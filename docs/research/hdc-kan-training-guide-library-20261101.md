# Training HDC and KAN Components Efficiently

An engineering guide for training hyperdimensional computing (HDC) and Kolmogorov-Arnold network (KAN) modules as lightweight plugins alongside a frozen LLM.

## Existing tools to start from

### HDC

- **torchhd**: the standard PyTorch library. It has encoders (Random, Level, Sinusoid, Projection), the MAP/BSC/HRR/FHRR VSA types, and classifiers (`Centroid`, `AdaptHD`, `OnlineHD`, `RefineHD`, `LeHDC`, `NeuralHD`).
- **hdlib** and **OpenHD**: alternatives. OpenHD is GPU-focused.
- Reference algorithms: OnlineHD (confidence-weighted single-pass updates), LeHDC (learns the class hypervectors by gradient descent with binary constraints), and resonator networks (for factorizing bound structures).

### KAN

- **pykan**: the reference implementation. It has grid refinement, pruning, and symbolic regression, but it is slow.
- **efficient-kan**: reformulates the layer as one batched matmul. Much faster than pykan.
- **FastKAN / FasterKAN**: replace B-splines with Gaussian RBFs or reflectional switch functions. Fastest on GPU.
- **ChebyKAN, JacobiKAN, KAT (Kolmogorov-Arnold Transformer)**: other basis choices. KAT uses rational bases with grouped weights, which is the main state-of-the-art route to KANs that scale.

## Training HDC

HDC is cheap to train if you stay in the right regime.

1. **Cache the encodings.** Encoding is the dominant cost, not learning. Encode your dataset once, store the hypervectors, and run every epoch over the cache.
2. **Initialize in one pass.** Bundle (sum) the encodings per class. This gives a working model after a single pass.
3. **Refine with a few perceptron-style epochs.** For each sample, update only on misclassification, or weighted by similarity error (`add_adjust` / `add_online` in torchhd). Typically 5 to 20 epochs are enough. Learning-rate decay helps.
4. **Pick D by sweep.** Try 1k, 2k, 4k, 8k. Accuracy usually plateaus well below 10k. Smaller D scales everything linearly.
5. **Learn the encoder when you can.** A random projection is the baseline. A trainable projection with a straight-through estimator through `sign()` (LeHDC-style) usually beats it at the same D, which means you can cut D.
6. **Quantize last.** Train with real-valued class vectors, then binarize and bit-pack for inference. Similarity becomes XOR plus popcount.
7. **For LLM features:** project a mid-layer hidden state with a random or learned matrix, then apply `sign()`. Mid layers tend to carry more usable structure than the final layer.

```python
import torch, torchhd
from torchhd.models import Centroid

D = 4096
enc = torchhd.embeddings.Projection(feat_dim, D)   # or Sinusoid / Level
clf = Centroid(D, n_classes)

H = enc(feats).sign()          # encode ONCE, cache this
clf.add(H, labels)             # single-pass bundling
for _ in range(10):            # corrective epochs
    clf.add_adjust(H, labels, lr=0.05)
```

## Training KAN

1. **Use a GPU-friendly basis.** For anything beyond toy size, use FastKAN (RBF) or Chebyshev rather than B-splines. The speedup is large and accuracy is usually comparable.
2. **Normalize inputs.** The grid has a fixed range, so put a LayerNorm in front, or update the grid from data samples (`update_grid_from_samples` in efficient-kan and pykan).
3. **Keep it small.** Grid size 5 to 8 and spline order 3. Narrow layers, such as `[in, 16, out]`, do most of the work.
4. **Train coarse to fine.** Train at a coarse grid, then refine the grid and warm-start the fine-grid coefficients by least-squares fit to the coarse function. This is cheaper than training the fine grid from scratch.
5. **Optimizer.** Adam for the bulk of training. pykan's LBFGS is excellent for small, precise numerical-fit problems (low-dimensional, smooth targets).
6. **Sparsify, then prune.** Train with L1 plus entropy regularization on the activations, prune dead edges and nodes, then fine-tune. This is where the inference savings come from.
7. **For exact numerical tasks:** fit, prune, then run `auto_symbolic` to replace the edges with closed-form functions or lookup tables. This is effectively zero-cost inference.
8. **Precision.** Train in bf16/fp16 for the matmul, but compute the basis expansion in fp32 if you see instability.

## Training them as plugins in your architecture

- **Train each module separately from the LLM.** Run the frozen LLM once over your data and save the features or hidden states to disk. Both HDC and KAN then train on the cached features, with no LLM in the loop. For hidden states, use llama.cpp's embedding output or HF transformers. LM Studio's chat endpoint doesn't expose them.
- **Define the module's interface target first.** This could be class labels (HDC router or memory), a numeric function (KAN), or a residual or logit correction. Train directly against that target.
- **Distill when the target is the LLM's own behavior.** For example, train the HDC router to match which tool or plugin the LLM would have picked.
- **Gate each module on measured end-to-end gain.** This matches your promotion rule for Tier 1. Log per-module latency and accuracy during training so the gate has data.

## Hardware notes (AMD R9700, 32GB)

These modules are small. HDC training is memory-bound, and with the encodings cached on the GPU the PCIe 3.0 link doesn't matter. KAN at the sizes above trains comfortably in 32GB of VRAM. HDC can even run on CPU.

The open question is whether PyTorch has a working ROCm build for the R9700 on Windows. Check the current ROCm-on-Windows PyTorch status. If it isn't usable, CPU plus a WSL2 ROCm attempt, or CPU-only for HDC, are your fallbacks.

## Next step

Pick the first module to train (HDC router, KAN numerical engine, etc.) and define its input and output format. From there, the concrete training loop and hyperparameter sweep follow directly from the sections above.