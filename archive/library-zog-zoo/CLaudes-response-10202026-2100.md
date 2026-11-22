User wrote:
>Here it is but I forgot to have Qwen test the HDC on the wikipedia data. I'll do that tomorrow.

Claude's response:
>This is a much better report than the earlier ones. It separates credit between the learned encoder and HDC, runs a real ablation (bow_flat vs hdc_text), caught the mixture-noise bug, and states its limitations. The main conclusions mostly hold up, but there are gaps. I’m going only on the report, not the code.
>
>What’s solid
>
>Binarized learned embeddings keep 91 to 95% of float top-1 at 1,024 bits. That matches what vendors report for binary quantization.
The dimension cliff and the extra sensitivity to bit-flip noise are plausible.
Random-word HDC does badly in this setup.
Problems
>
>“At chance” has no positive control. Show that hdc_text can retrieve when the answer is known, such as querying with the passage’s own text or with 30% of its words dropped. If it fails that, it’s a bug. If it passes, you’ve shown the encoder works.
Capacity probably explains the failure. Your own H3 found one hypervector holds roughly D/18 items, about 57 at D=1,024. Passages bundle 100 to 300 words. So the encoder is overloaded by design, which fits the result, and position binding makes it worse. Test D=10,000 and shorter units like sentences. That would show whether the cause is capacity, not HDC itself. Bigger D costs memory, so it’s a diagnostic, not a recipe.
No BM25. bow_flat is an unweighted, sign-saturated bag of words, a weak lexical retriever. BM25 is the standard reference and easy to add.
No nDCG@10. BEIR’s standard metric would let you compare your float baseline to Cohere’s published numbers (scifact 71.81, nfcorpus 38.63, fiqa 42.14, android 50.01). That’s the best check that the harness is correct.
“Bit-identical” isn’t robustness. It shows determinism. With 300 to 700 queries, top-1 has roughly ±3 points of sampling error, so 1 to 3 query differences are noise. Run multiple random-projection seeds.
Internal slips. Section 0 says 30 to 48% at D=128, but Q5 says 15 to 30%. Some quoted ranges don’t match the tables (for example, bow_flat is about 9 to 40% of baseline in the headline table, not 4 to 44%). Small, but they matter.
The credit rule is broken in the summary. Section 2 says the embedding pipelines are never credited to HDC, yet Section 0 calls the working recipe “HDC-native.” Binarized embeddings plus Hamming search is standard binary quantization. HDC’s only link is the ±1 format.
My answers to the key questions
>
>Q1: The baseline is fine as a retrieval baseline, but it isn’t “current AI.” Add BM25.
Q2: Random word vectors are a lower bound. Standard options include character n-gram encodings, and larger D (typically around 10k) is the HDC norm.
Q3: My earlier estimate was for random independent items. Real embeddings cluster, so agreement is partly coincidence. Don’t count it as confirmation.
Q4: I agree for this regime only, at D≤1,024 with whole-passage bundling. A passed positive control plus a loss to BM25 at large D would make it solid.
Q5: Overclaim. Also add binary shortlist plus float rescoring, which is the standard fix for binary recall loss.
Q6: K1 is a fine start. Use parameter-matched, tuned MLPs, several seeds, and an extrapolation test. Replace the human-rated K2 with an objective one: does it recover the ground-truth formula?
Tomorrow
>
>The Wikipedia test would repeat what BEIR already shows. I’d run these first, in order: positive control, D=10k with sentence units, BM25, nDCG@10 versus the published scores, multiple seeds, and binary-plus-rescoring. KAN stays on hold until those are done.

User wrote:
>It seems like you have more knowledge on HDC that you should tell me to improve my HDC and eventually my KAN such as what are standards that could potentially be missing in my HDC code? You said BM25 is a standard reference. Then you say there is no nDCG@10. What else should I add on to the HDC so it can run accurately and that it can perform well. You stated add positive control, test if D=10,000 but is D a fixed value or can it be adjusted according to the task at hand, and what can improve the HDC's algebraic composition? Also, you seem to play it safe in regards to data factuality and I have noticed you do not like to entertain future possibilities that are not tested and proposed formally, but I ask you, do you know of the standard HDC practices that can help improve my HDC?

Claude's response:
>Fair challenge. I label what’s established versus guessed because a wrong guess costs you days of testing, but speculation is welcome when it’s labeled. Below is both. It’s mostly from my background knowledge, so check it against the standard survey (see the end).
>
>BM25 vs. nDCG@10. They’re different kinds of things. BM25 is a classic keyword-search method, a competitor to beat. nDCG@10 is a metric, a way to score how good a method’s top-10 list is. You want both, and I didn’t contradict myself.
>
>Is D fixed? No. D is a design choice you set per task. Capacity and noise tolerance grow roughly with D, while memory and compute grow too. Sweep it, find the knee, and add a safety margin, as you did. Vectors of different D can’t be bound directly. Use multiples of 64 bits for hardware-friendly operations.
>
>Standard practices you may be missing
>
>Pick a model family on purpose. The survey lists Binary Spatter Codes, Multiply-Add-Permute, Holographic Reduced Representations, Sparse Block Codes, and others. Your XOR and convolution tests mix two of them. From memory, the complex-valued variant (FHRR) unbinds almost exactly. Plain convolution’s heavy-tailed noise, like your 0.17 minimum, is a known weakness. 
arxiv
Bundle with integer counters. Keep a running sum and binarize only at the end. Handle ties from even counts with a random tie-break. Weight words by IDF and drop stopwords.
Use permutation for order. Cyclic shifts, not XOR with random position vectors. N-gram windows (bind shifted word or letter vectors, bundle them) keep partial matches alive, which is the problem behind your F2.
Add a cleanup memory. After unbinding, snap the noisy result to the nearest known symbol. This turns “0.77 similar” into an exact answer, and it’s the main fix for composition.
Test records. Store role⊗filler pairs bundled together (k = 3 to 20 pairs), then unbind a role and clean up. Measure accuracy against k and D. Single-pair binding is too easy.
Factor multi-bound items with resonator networks. From memory: an iterative method for decoding several bindings at once.
Compare at equal memory (bytes per item), not equal D. Multi-bit vectors at smaller D might beat 1-bit at larger D. Untested, but easy to check.
Speculative ideas (mine, untested)
>
>HDC function heads for your KAN question. Fractional power encoding represents numbers so similarity decays smoothly, which gives a cheap regression method. That’s in the literature, but pitting it against KAN and a quantized MLP on symbolic formulas is my suggestion. It maps well to FPGAs.
Learned encoder trained for HDC. Train a small encoder so binding and bundling behave well, with unbinding accuracy in the loss.
HDC records as working memory for multi-hop questions. I suspect a plain dictionary wins unless the cues are noisy.
Where to read. The two-part survey is the reference: Part I covers models and transformations of data types into hypervectors, and Part II covers applications, cognitive models, and challenges. It’s free on arXiv (2111.06077 and 2112.15424). Reading it locally keeps your data private, and Qwen can summarize chapters from the PDFs you give it.