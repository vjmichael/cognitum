6/15/26, 9:17 PM   
Al Research Grant Opportunities - Google Gemini 

Target Al Architecture: Data Ingestion Specifications 

To successfully transition from 11ama.cpp inference extraction to training your specialized target models, the raw binary tensor dumps must be transformed into specific structural formats. Below are the required shapes, data types, and ingestion methods for each target Al. 

1. HDC (Hyperdimensional Computing) Vectors 

HDC does not process continuous floating-point numbers well; it relies on massive, binary (or bipolar) orthogonal vectors to perform symbolic logic via XOR and addition operations. 

**Raw Output:** Float32 array, Shape: [1, d] (e.g., [1, 4096] ). 

• 
**Required Target Format**: Bit-packed boolean or integer array, Shape: [1, D] (where D > 10,000). 

**The Formatting Bridge**: 

1. Multiply the raw [1, d] vector by a static Random Projection Matrix to scale it up to 
[1, 10000] . 

2. Apply a sign threshold: if value > 0, set to 1; if < 0, set to 0. 

3. **Crucial Step:** Pack these bits into uint64 arrays using numpy.packbits. Do not store 
10,000 floats; store ~156 uint64 integers. 

4. **Ingestion:** The HDC student model ingests these uint64 arrays directly to perform 
hyperdimensional binding. 

**Advanced Goal:** Implement Associative Memory Banks using holographic binding and XOR-summation to create non-decaying memory storage, bypassing the linear bottleneck of recurrent states.

2. KAN (Kolmogorov-Arnold Models) Compositional Curricula 

KAMS replace static weights with learnable B-splines. They need to learn the mathematical mapping from the input of an MLP to the output of an MLP. 

• 
**Raw Output:** Two unlinked continuous Float32 arrays: MLP_Input and MLP_Output. 

**Required Target Format**: Paired Input-Output Tensors, batched into standard 
.safetensors.   
||   
Tit   
玷 

E 

• 
**The Formatting Bridge:** 

1. The Python script must strictly pair (X, Y) where X is the tensor going into the layer 
and Y is the tensor coming out. 

2. Format as Safetensors with keys: {"input" : tensor_X, "target": tensor_Y, 
"complexity_score": scalar} . 

3. **Ingestion:** Your PyTorch dataloader for the KAM must load these sorted pairs and feed 
them into the B-spline grid optimization loop, starting with the lowest 
complexity_score (curriculum learning). 

3. SCM (Structural Causal Models) Dependency Graphs 

https://gemini.google.com/app/fa3ace6b27cb5e56   
1/3   
6/15/26, 9:17 PM   
Al Research Grant Opportunities - Google Gemini SCMs do not train on sequential tokens; they train on Directed Acyclic Graphs (DAGs) and 
counterfactual deltas. 

• 
**Raw Output:** Float arrays representing activation patched nodes and the resulting output logit shifts. 

**Required Target Format:** Adjacency Matrices and Node Dictionaries. 

• 
**The Formatting Bridge**: 

1. Convert the delta data into a sparse adjacency matrix format (e.g., scipy.sparse CSR 
matrices or PyTorch Geometric edge_index formats). 

2. Shape: [2, num_edges] where row O is the source node (e.g., Attention Head 4) and 
row 1 is the destination node (e.g., MLP Layer 12). 

3. **Ingestion:** The student model must be built using a Graph Neural Network (GNN) 
framework like PyTorch Geometric (PYG), which ingests this edge_index format natively to enforce causal routing. 

**Strategic Utility:** Use the resulting DAGs as a Causal Truth Filter. Incoming data is validated against established causal laws; contradictions are flagged as "dishonest" or "low-confidence" before updating long-term weights.

4. Capsule Equivariance Paraphrase Pairs 

Capsule networks separate a concept's existence (vector magnitude) from its traits (vector phase/orientation). They must be trained on contrastive pairs. 

• 
**Raw Output:** Two Float32 vectors from different token sequences (Sequence A and Sequence A-Paraphrased). 

**Required Target Format:** Triplet structured data. 

**The Formatting Bridge**: 

1. Group the extracted tensors into [Anchor, Positive, Negative] triplets. 

2. Format: Tensor Shape [batch_size, 3, capsule_dim] . 

3. Ensure the data is normalized: you must explicitly separate the vector into its L2-norm 
||v|| and its directional unit vector v/ ||v|| inside the Safetensor file. 

4. **Ingestion:** The Capsule network uses a custom "Margin Loss" for the magnitude and a 
"Cosine Similarity Loss" for the phase, requiring both components to be pre-calculated or explicitly split in the dataloader. 

**Truth Filtering:** Utilize [Anchor, Positive, Negative] triplets to explicitly train the model on the boundary between factual accuracy and deceptive misinformation.

5. SSM Temporal Coherence Traces 

State Space Models (like Mamba) are recurrent. They train on the evolution of a hidden state over time, not on isolated snapshots. 

• 
**Raw Output:** Individual Aht trace files from the C++ inline callback. 

• 
**Required Target Format:** Time-series chunked sequences. Shape: [batch_size, sequence_length, hidden_dim] . 

**The Formatting Bridge:** 

1. You cannot feed these into the target Al one token at a time; disk I/O will stall the GPU. 

2. Your Python script must stitch the individual Aht binary files back together into 
contiguous temporal blocks (e.g., chunks of 2048 time steps). 

https://gemini.google.com/app/fa3ace6b27cb5e56   
2/3   
6/15/26, 9:17 PM   
Al Research Grant Opportunities - Google Gemini 

3. Save as multi-dimensional Float16 Safetensors. 

4. **Ingestion:** The student SSM natively ingests the [sequence_length] dimension, using it 
to teach its internal recurrent transition matrices (the A and B matrices in Mamba) how 
to evolve optimally over time. 

3/3   
https://gemini.google.com/app/fa3ace6b27cb5e56 

---

## Cognitive Architecture Synergy & Memory Management

To overcome the "struggle to remember" and achieve sub-linear scaling with Transformer-level reasoning, these components are integrated as follows:

1. **Memory Storage (HDC)**: Instead of evolving a single state, the model uses HDC's holographic maps for long-term associative memory, allowing high-precision retrieval without decay.
2. **Sequential Flow (SSM)**: The SSM layer handles temporal coherence and linear scaling over time, ensuring the model can process massive contexts efficiently.
3. **Logical Verification (SCM)**: SCMs provide a "Truth Gate," filtering out noise and misinformation by verifying that new data adheres to causal structures.
4. **Nuance & Equivariance (Capsules)**: Capsule Networks manage concept orientation and phase, providing the model with a high-fidelity understanding of properties and traits, distinguishing subtle factual differences from general correlations.

## Dynamic Learning & Epistemic Gating

The architecture implements a dynamic learning loop to ensure data integrity:

- **Epistemic Uncertainty Gating**: The model assigns an uncertainty score to new information. If "surprise" is high but causal evidence (via SCM) is missing, the data is sequestered for further scrutiny rather than integrated into core weights.
- **Causal Truth Filtering**: All updates to long-term memory must pass a causal consistency check, preventing the model from being "poisoned" by dishonest or contradictory information.
- **Contrastive Truth Training**: Using Capsule triplets, the model is explicitly taught the difference between truth and falsehood, moving beyond simple probability-based prediction toward principled reasoning.