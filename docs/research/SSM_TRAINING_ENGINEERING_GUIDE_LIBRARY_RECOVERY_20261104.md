# Training a State Space Model (SSM): A Detailed Engineering Guide

This guide covers how to train SSMs end to end: Mamba-1, Mamba-2 (SSD), and the S4/S5 family, plus the closely related linear-recurrent layers (GLA, DeltaNet, Gated DeltaNet, RWKV). It is written in plain language first, with the mechanics second, and contains no code. Use it as the plan you hand to whoever (or whatever) writes the implementation.

---

## 1. Existing tools and the current state of the art

Do not write an SSM trainer from scratch if you can avoid it. These are the standard building blocks.

| Tool | What it gives you | Notes |
|---|---|---|
| **mamba-ssm** (state-spaces/mamba) | Reference Mamba-1 and Mamba-2 (SSD) layers, fused kernels, language-model wrappers, pretrained checkpoints | CUDA-first. Check its README for current ROCm status. |
| **mambapy** | Pure-PyTorch Mamba with a parallel scan | Runs on any PyTorch backend. Slower, fine at small scale. |
| **flash-linear-attention (fla)** | Triton kernels and layers for Mamba-2, GLA, DeltaNet, Gated DeltaNet, RWKV, RetNet, HGRN and others, plus training utilities | Triton is the most portable high-performance route to non-NVIDIA GPUs. |
| **state-spaces/s4** | S4, S4D, S5-style layers, Long Range Arena (LRA) benchmarks | Best for non-language sequence tasks. |
| **Hugging Face transformers** | Mamba and Mamba-2 model classes, Trainer integration, PEFT/LoRA | Falls back to slow pure-PyTorch paths when fused kernels are missing. |
| **Zoology** (HazyResearch) | Synthetic benchmarks, especially multi-query associative recall (MQAR), for testing recurrent layers | Use it to validate a layer before spending compute. |
| **Megatron-LM / NeMo, TorchTitan, lit-gpt-style trainers** | Multi-GPU training infrastructure that several SSM and hybrid recipes run on | Relevant only when you outgrow a single GPU. |

**State-of-the-art orientation (verify against current releases, this area moves fast):**

- Pure SSM language models are competitive at small to medium scale. The strongest recent results come from **hybrids**: mostly SSM layers with a small number of attention layers (Jamba, Zamba, Samba, Nemotron-H and similar families). A typical ratio is roughly one attention layer for every four to eight SSM layers.
- **Mamba-2 / SSD** is the preferred training formulation because it turns most of the work into matrix multiplications that run on tensor cores.
- **Gated DeltaNet and related delta-rule layers** are the current go-to when the task needs precise overwrite or update of stored values (see section 14).
- **Distilling or converting a trained transformer** into an SSM or hybrid (Mamba-in-the-Llama, MOHAWK/Phi-Mamba, LoLCATs-style methods) is dramatically cheaper than pretraining from scratch (see section 11).

---

## 2. How to think about an SSM without the heavy math

An SSM layer is a **bank of leaky memories** that read a sequence one step at a time.

- The **state** is a fixed-size notebook. Its size does not grow with the sequence length.
- At every step the layer does three things: it **forgets** a little of the notebook, it **writes** something about the current input into it, and it **reads** from it to produce an output.
- **A** controls forgetting. Think of it as a per-channel time constant: some channels remember for a few steps, others for thousands. A is kept negative so that memories fade instead of exploding.
- **Δ (delta, the step size)** is how long the "shutter" stays open on this input. A large Δ means "this token matters, overwrite and absorb it strongly, forget faster". A small Δ means "skip this token, keep the old memory."
- **B** is the write gate: which slots of the notebook this input writes into.
- **C** is the read gate: which slots of the notebook feed the output.
- In **selective SSMs (Mamba)**, Δ, B and C are computed from the current input. The model decides, token by token, what to store and what to ignore. In **time-invariant SSMs (S4, S5)**, they are fixed, so the layer behaves like a very long learned filter.

Why this matters for training: because the update is **linear in the state**, you never have to actually run the sequence step by step during training. The whole sequence can be processed in parallel with a scan or with block matrix multiplications, and at inference you switch to the cheap one-step-at-a-time form. Training and inference compute the same function two different ways. That fact is also your best correctness test (section 10).

---

## 3. The three computation modes

| Mode | Used for | How it works |
|---|---|---|
| **Convolutional** (S4, S4D, S5, other time-invariant layers) | Training | The recurrence is unrolled into one long learned kernel and applied to the whole sequence with an FFT. |
| **Parallel scan** (Mamba-1) | Training | Because the update is linear it can be re-bracketed as an associative operation. A GPU kernel scans the sequence in parallel inside fast on-chip memory, and the backward pass recomputes intermediate states instead of storing them. |
| **Chunked matrix form** (Mamba-2 / SSD) | Training | The sequence is cut into chunks (256 by default in the reference code). Inside a chunk the layer is computed like a masked attention matrix multiply. Between chunks only a small state is passed along. Most of the arithmetic runs on tensor cores. |
| **Recurrent step** | Inference, state tracking, streaming | One token in, one state update, one output. Constant memory and constant time per token. |

Decision rule: train in the parallel form (scan or SSD), deploy in the recurrent form. Never train in the recurrent form except for tiny experiments, since it cannot use the GPU efficiently.

---

## 4. Block anatomy (what you are actually training)

A Mamba-style block, in the order data flows through it:

1. **Pre-norm** (RMSNorm) on the residual stream.
2. **Input projection** that widens the model dimension by an expansion factor (default 2) and splits the result into a main branch and a gate branch. In Mamba-2 the same projection also produces B, C and Δ.
3. **Short causal depthwise convolution** (kernel width 4) followed by SiLU on the main branch. It gives the layer a few tokens of local context before the SSM sees the input. In Mamba-2 it is applied jointly to x, B and C.
4. **Selective SSM core**: compute Δ (softplus of a projection plus a bias), discretize A and B with Δ, run the scan or SSD, add the skip term D times the input.
5. **Gating**: multiply the SSM output by SiLU of the gate branch. Mamba-2 applies a normalization (gated RMSNorm) here.
6. **Output projection** back to the model dimension, added to the residual stream.

**Parameter budget:** the two big projections dominate. For Mamba-1 with expansion 2, a layer has about 6 times d_model squared parameters, roughly half of a transformer layer (12 times d_model squared). The Mamba paper compensates by using about twice as many layers as a transformer of the same parameter count. When you size a model, count layers, not just width.

**Mamba-2 specifics:** A is a single scalar per head instead of a matrix per channel, the state is larger (64 to 128 per head versus 16), heads have a fixed size (64 by default), and B and C can be shared across heads in groups (ngroups, default 1). These choices are what make the matmul form possible.

---

## 5. Parameterization and initialization (where most training runs are won or lost)

These details are not optional. SSMs are far more sensitive to them than transformers.

**A (the forgetting rates)**
- Store A as a log value and compute A as the negative exponential of it. This guarantees A stays negative, so memories decay rather than blow up, regardless of what the optimizer does.
- Mamba-1 initializes each channel's state dimensions to the sequence 1, 2, 3, ... N (the "S4D-Real" initialization), so different state slots have different decay speeds. Mamba-2 draws a per-head value from a range (1 to 16 by default). Both give you a spread of short and long memories on day one.
- For time-invariant layers (S4/S5), use the HiPPO-derived initializations (HiPPO-LegS, S4D-Lin). They are designed so the state starts out as a good compressed summary of recent history.

**Δ (the step size)**
- Initialize Δ so that, after the softplus, it falls log-uniformly between about 0.001 and 0.1. This is done by choosing the bias of the Δ projection as the inverse softplus of sampled values. Clamp the floor (the reference uses 1e-4).
- Reason: the product of Δ and A is the per-step decay. This range spreads memory timescales from a handful of tokens up to hundreds or thousands.
- In Mamba-1, Δ is generated through a low-rank bottleneck (rank about d_model divided by 16). Initialize the projection weights so the Δ output starts small and stable.

**D (skip connection)**: initialize to ones.

**Everything else**: standard transformer-style initialization. Scale the output projections by one over the square root of the number of layers (the GPT-2 style residual scaling), because the same residual-depth issue applies.

**Embedding and head**: tie them (share weights) for small models. It saves parameters and usually helps.

---

## 6. Optimizer, schedule and batch

**Optimizer:** AdamW with betas 0.9 and 0.95, epsilon 1e-8, gradient clipping at norm 1.0.

**Weight decay:** 0.1 for the large weight matrices. **Exclude from decay:** the log-A parameter, D, all biases (including the Δ bias), normalization weights, and usually the embeddings. Decaying A or the Δ bias pulls the memory timescales toward arbitrary values and quietly degrades the model.

**Learning rate:**
- The Mamba paper trained with learning rates several times higher than the GPT-3 recipe (on the order of 5x). Typical starting points: about 1e-3 to 3e-3 for tiny models (a few million parameters), around 6e-4 for 125M, falling as models grow.
- Time-invariant S4-family layers conventionally train their SSM parameters (A, B, Δ) at a smaller learning rate than the rest of the network (about 1e-3 maximum, and no weight decay).
- Always sweep the learning rate on a small proxy model first. Try three values spaced by a factor of about 2 to 3 and pick the best. This is the single highest-return experiment.

**Schedule:** linear warmup over 1 to 2 percent of steps (at least a few hundred steps), then cosine decay to about 10 percent of the peak. For short runs, a warmup of 100 to 500 steps is enough.

**Batch size:** measure in tokens, not sequences. Around 0.25M to 1M tokens per step is standard for pretraining at 100M to 1B parameters. For small plugin models and synthetic tasks, 16k to 128k tokens per step is plenty. If your GPU memory limits the micro-batch, use gradient accumulation to reach the target token count.

**Dropout:** none for pretraining. For small supervised tasks with limited data, a small amount (0.0 to 0.1) in the projections can help.

---

## 7. Precision and numerical stability

- Keep the **recurrence, the state, and the SSM parameters (A, D, Δ-related) in fp32**. The reference implementation recommends fp32 master parameters with automatic mixed precision, because the recurrent dynamics are sensitive to rounding. The large matrix multiplies can run in bf16.
- Prefer **bf16 over fp16**. fp16 has a narrow range and needs loss scaling; bf16 does not.
- If you write or modify a scan yourself, accumulate in fp32 and only cast the output back down.
- Compute Δ via softplus with a numerically safe implementation (large inputs should pass through unchanged instead of overflowing).
- Log the gradient norm every step. A sudden climb usually precedes a loss spike by tens to hundreds of steps and gives you time to react.

---

## 8. Data preparation

**For language modeling**
- Tokenize with a standard BPE tokenizer and **pack** documents into fixed-length sequences. Insert an end-of-document token between documents.
- Because an SSM carries state forward, state can leak across document boundaries inside a packed sequence. Either reset the state at boundaries (the reference kernels accept sequence-boundary indices for this) or accept the leakage and keep the end-of-document token as the learned reset signal. Resetting is cleaner.
- Context length: 2k to 4k is a good training length. SSMs often extrapolate to longer sequences at inference, but only if trained with enough variety in memory timescales. Include some longer training sequences if you need long-range behavior.
- **Sequence-length warmup** (starting at 512 or 1k and growing to the target) speeds early training and stabilizes it.

**Token budget:** the Chinchilla rule of about 20 tokens per parameter is a compute-optimal minimum. For small models you intend to deploy, train far longer (100 to 1000 or more tokens per parameter). Small models keep improving.

**For synthetic or structured tasks (state trackers, event streams)**
- Define a small, explicit vocabulary of event tokens.
- Generate data from a program so that every sequence comes with exact ground truth.
- Mix lengths in each batch so the model cannot overfit to one length.
- Hold out entire length regimes (longer than anything in training) as a dedicated test set.

---

## 9. Training loop procedure

1. **Overfit one batch first.** The loss should go to near zero within a few hundred steps. If it does not, there is a bug in the model, the data or the loss, and nothing else is worth tuning yet.
2. **Run the parallel-versus-recurrent equivalence test** (section 10) on the untrained model.
3. **Learning-rate sweep** on a tiny version of the model (a few million parameters, a few thousand steps).
4. **Short full-config run** (1 to 5 percent of the planned compute) to check throughput and loss curve shape.
5. **Full run** with checkpoints every N minutes, including optimizer state, scheduler state, random-number-generator state and the data-loader position, so you can resume exactly.
6. **Evaluate periodically** on held-out perplexity or task accuracy, and on length-extrapolation sets.
7. **Average the last few checkpoints** (or use exponential moving average weights) for the final model. It is free quality.

**Throughput levers**
- Make d_model, head size and state size multiples of 8, preferably 64 or 128, so tensor cores are used.
- Prefer Mamba-2/SSD over Mamba-1 when you need speed: more of the work becomes matmul.
- Compile the model graph where your backend supports it, but keep the fused SSM kernel as a black box.
- Use activation (gradient) checkpointing per layer if memory is the constraint. The fused kernels already recompute internally.
- Track tokens per second and the fraction of time the GPU is busy. If utilization is low, the data loader or the CPU is the bottleneck, not the model.

---

## 10. Validation tests to run before trusting a model

1. **Parallel versus recurrent equivalence.** Feed the same sequence through the training (parallel) path and through the one-token-at-a-time inference path. Outputs must match to within numerical tolerance, including the convolution state and the SSM state. A mismatch means a bug in state handling, and it will show up later as "works in training, fails when deployed."
2. **Chunk invariance.** Split a long sequence into pieces, carrying the state across pieces. The result must equal processing it whole.
3. **Gradient sanity.** Confirm the gradients flow to A, Δ, B, C and D. A parameter whose gradient is always zero is disconnected.
4. **Synthetic recall benchmarks.** Selective Copying, Induction Heads and MQAR are the standard smoke tests. A small model should solve the first two almost perfectly. MQAR measures how much the state can store: accuracy as you increase the number of key-value pairs tells you the effective memory capacity.
5. **Length extrapolation curve.** Plot loss or accuracy versus position and versus total length beyond the training length.
6. **Throughput and memory at inference.** Measure latency per token and state size per session. These are the numbers that justify using an SSM in the first place.

---

## 11. Starting from an existing transformer instead of from scratch

If you already have a good pretrained transformer, converting is cheaper than pretraining.

- **Mamba-in-the-Llama:** initialize the SSM's projections from the transformer's attention projections (queries map to the read gate C, keys to the write gate B, values to the input x), keep the MLP layers, replace some or all attention layers, then train with progressive distillation. Layers are swapped gradually, followed by supervised fine-tuning and preference-style distillation. Hybrid results (keeping a few attention layers) are strongest.
- **MOHAWK / Phi-Mamba:** a three-stage process that aligns the matrices of the SSM with the attention matrices, then aligns hidden states layer by layer, then does end-to-end knowledge distillation. It needs only a small fraction of the original pretraining tokens.
- **LoLCATs and related linear-attention conversion:** replace softmax attention by a linear-recurrent layer, train it to mimic the attention output layer by layer, then recover quality with a low-rank adaptation.
- General recipe: freeze most of the teacher, train the new layers to match teacher hidden states or output logits, then unfreeze and fine-tune end to end at a low learning rate.

---

## 12. Fine-tuning a pretrained SSM

- Parameter-efficient fine-tuning works on SSMs. LoRA on the large input and output projections is the safe default, and the Hugging Face PEFT library supports Mamba modules. Research on Mamba-specific PEFT (for example MambaPEFT) reports that adapting the projections, plus selected SSM-specific parameters, can match or beat full fine-tuning.
- Keep A, D and the Δ bias frozen unless you have a reason to move them.
- Use a learning rate 5 to 10 times lower than pretraining for full fine-tuning.
- Keep the recurrence in fp32 even when the rest is quantized or in low precision.

---

## 13. Training on long streams and carrying state

For sequences far longer than fits in memory (event logs, continuous sessions):

- Train on **segments** and pass the final state of one segment as the initial state of the next. Detach the carried state from the graph so gradients only flow within a segment (truncated backpropagation through time).
- Randomize segment boundaries and occasionally reset the state during training so the model works from a cold start as well as from a warm one.
- Use varied segment lengths so the model does not learn to rely on a fixed position.
- To get gradients that reach farther back, increase the segment length rather than backpropagating across segment boundaries.
- At inference you can simply keep the state alive for as long as you want, and snapshot or restore it, since it is a fixed-size tensor per layer.

---

## 14. Choosing the layer type by what the state has to do

This is where the plugin and state-tracker use case differs from language modeling.

| What the state must do | Layer choice to try |
|---|---|
| Summarize recent context, general language modeling | Mamba-2 (SSD), or a hybrid with a few attention layers |
| Long-range filtering of continuous signals (audio, sensors, time series) | S4D / S5 / LRU time-invariant layers |
| Store and **overwrite** specific values (set variable X to 5, update entry Y) | Delta-rule layers: DeltaNet, Gated DeltaNet (fla). They update a key-value memory by correcting it, rather than only decaying and adding. |
| **Count or compose** updates (modular counters, permutations, swaps) | Layers whose transition can have negative eigenvalues or be input-dependent beyond a positive decay: the negative-eigenvalue variants of Mamba and DeltaNet, and RWKV-7. fla includes these. |
| Exact retrieval of many items (associative recall) | Larger state, more heads, and a hybrid with a small number of attention layers |

Practical approach: build the data generator first, then run the same task through two or three candidate layer types from fla and pick the cheapest one that reaches the accuracy you need. The swap is cheap because they share a common interface.

---

## 15. Training an SSM state-tracker plugin: concrete plan

This is the case most relevant to a modular system where the SSM sits beside an LLM.

**Define the interface**
- Input: a stream of structured **event tokens** (one token or a short fixed group per event), optionally combined with features derived from the LLM.
- Output: the **current state** after every event, as a set of fields (for example, the value of each tracked variable). Decode it with one small classification head per field.
- Contract: `reset`, `update(events)`, `read_state`, `snapshot`, `restore`. The recurrent step form implements all of these natively because the state is a fixed-size tensor.

**Build the data generator**
- Write a simulator of the process you want to track. It produces random event sequences and, at every step, the exact ground-truth state.
- Support several operation types (set, copy, update, reset) with configurable proportions, so you can change difficulty without rewriting anything.
- Include distractor events that should not change the tracked state.

**Supervise densely**
- Compute the loss at every step on every state field. It yields many times more gradient signal per sequence than a single question at the end.
- Optionally add occasional "query" events whose answer requires reading the state, to train the read path.

**Curriculum**
1. Short sequences (16 to 32 events), few variables, simple operations.
2. Grow the length gradually to the maximum, and increase the number of variables.
3. Add the harder operation types last.
4. In the final stage, train on mixed lengths with a held-out set that is longer than anything seen.

**Sizing a first model:** d_model 256, 4 to 8 layers, expansion 2, state size 16 (Mamba-1) or 64 (Mamba-2). That is a few million parameters, trains in minutes to hours on a single GPU, and fits in a tiny fraction of 32 GB. Scale only if accuracy plateaus below target.

**Metrics:** per-field accuracy, **full-state accuracy** (all fields right at once), accuracy by position, accuracy by length, and accuracy after a deliberate state reset. The one that matters is full-state accuracy at lengths beyond training.

**Promotion criterion for a plugin:** measure the end-to-end task result of the larger system with and without the plugin, not only the plugin's own accuracy. Log latency per event and state size per session as part of the same evaluation.

---

## 16. Troubleshooting

| Symptom | Likely causes and fixes |
|---|---|
| Loss is NaN early | Learning rate too high; fp16 used instead of bf16; A became non-negative (use the log parameterization); Δ softplus overflow; missing gradient clipping. |
| Loss spikes mid-run | Learning rate too high for the current phase; weight decay applied to A or Δ bias; very long sequence suddenly introduced. Lower the peak LR, add or tighten clipping, restart from the last good checkpoint. |
| Loss plateaus high | Initialization of A or Δ off; model too small for the state it must hold; data not shuffled; too little training. Increase the state size or heads first. |
| Works in training, fails at inference | Convolution state not carried between steps; state not reset at document boundaries consistently; different precision in the two paths. Run the equivalence test. |
| Good on short sequences, poor on long | Training lengths too uniform; memory timescales too short (check the Δ init range); not enough long sequences in the mix. |
| Slow training | Dimensions not multiples of 8 or 64; fused kernel not in use (silent fallback to the pure-PyTorch path); data-loader bound. |
| Out of memory | Smaller micro-batch with accumulation; per-layer gradient checkpointing; shorter sequence with state carrying; smaller expansion. |

---

## 17. Hardware notes for a single AMD GPU with 32 GB

- Mamba-1's original fused kernels are CUDA-centric. For an AMD card, the practical routes are, in order: (1) fla's Triton kernels with a working ROCm build of PyTorch, (2) the pure-PyTorch parallel-scan implementations (mambapy) or the minimal chunked SSD reference, which are slower but sufficient for plugin-scale models, (3) CPU training for tiny models.
- Confirm the current state of ROCm PyTorch support for your exact GPU and operating system before planning a run. If it is not available, the pure-PyTorch route on CPU or through whatever backend works is the fallback, and a plugin-sized model still trains in a reasonable time.
- Inference does not need the fused training kernels. The recurrent step is a handful of small operations and runs on any backend.
- Models of the size suggested in section 15 are limited by data generation and evaluation speed, not by memory.

---

## 18. One-page checklist

1. Pick the layer family from section 14, using fla for quick side-by-side trials.
2. Write the data generator or tokenization and packing pipeline, with dense per-step labels where possible.
3. Parameterize A as a negative exponential of a stored log value. Initialize A with spread-out timescales and Δ log-uniformly in 0.001 to 0.1.
4. AdamW (0.9, 0.95), weight decay 0.1 on matrices only, clip at 1.0, warmup then cosine.
5. Fp32 for the recurrence and SSM parameters, bf16 for the big matmuls.
6. Overfit one batch. Run the parallel-versus-recurrent equivalence test.
7. Sweep the learning rate on a tiny model. Then run the full configuration.
8. Train with a length curriculum and, for streams, with carried and detached state.
9. Evaluate on held-out lengths, recall benchmarks and end-to-end task results.
10. Deploy in the recurrent form, and snapshot the state as a plain tensor.
