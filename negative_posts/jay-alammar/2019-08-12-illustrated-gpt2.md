---
source_type: technical_blog
author: Jay Alammar
author_id: jay-alammar
title: The Illustrated GPT-2 (Visualizing Transformer Language Models)
date: '2019-08-12'
source_url: https://jalammar.github.io/illustrated-gpt2/
download_url: https://raw.githubusercontent.com/jalammar/jalammar.github.io/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_posts/2019-08-12-illustrated-gpt2.md
repository_url: https://github.com/jalammar/jalammar.github.io
repository_revision: e4dbd4bb1cd3f05375d842b6c12f69ff37b01475
source_path: _posts/2019-08-12-illustrated-gpt2.md
license: CC-BY-NC-SA-4.0
license_url: https://creativecommons.org/licenses/by-nc-sa/4.0/
license_evidence_url: https://github.com/jalammar/jalammar.github.io/blob/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_layouts/default.html#L85
maximum_words: 750
retrieved_at: '2026-10-02T04:59:14.898490+00:00'
source_sha256: d41fe4c681fcece585553f542f102843cd14162ffe77d6fe5745c534359bc465
sample_sha256: 1439566c0565caadb134c22a62ac78e9c53ae9410964e30ce8766a01b7281b6c
sampling: Contiguous sentence-complete prose excerpt, 150–750 whitespace words; markup/code/navigation/quoted
  blocks/equations removed.
excerpt_words: 742
excerpt: true
---

This year, we saw a dazzling application of machine learning. The OpenAI GPT-2 exhibited impressive ability of writing coherent and passionate essays that exceed what we anticipated current language models are able to produce. The GPT-2 wasn't a particularly novel architecture -- it's architecture is very similar to the decoder-only transformer. The GPT2 was, however, a very large, transformer-based language model trained on a massive dataset. In this post, we'll look at the architecture that enabled the model to produce its results. We will go into the depths of its self-attention layer. And then we'll look at applications for the decoder-only transformer beyond language modeling.

My goal here is to also supplement my earlier post, The Illustrated Transformer, with more visuals explaining the inner-workings of transformers, and how they've evolved since the original paper. My hope is that this visual language will hopefully make it easier to explain later Transformer-based models as their inner-workings continue to evolve.

Part 1: GPT2 And Language Modeling
What is a Language Model
Transformers for Language Modeling
One Difference From BERT
The Evolution of The Transformer Block
Crash Course in Brain Surgery: Looking Inside GPT-2
A Deeper Look Inside
End of part #1: The GPT-2, Ladies and Gentlemen
Part 2: The Illustrated Self-Attention
Self-Attention (without masking)
1- Create Query, Key, and Value Vectors
2- Score
3- Sum
The Illustrated Masked Self-Attention
GPT-2 Masked Self-Attention
Beyond Language modeling
You've Made it!
Part 3: Beyond Language Modeling
Machine Translation
Summarization
Transfer Learning
Music Generation

So what exactly is a language model?
What is a Language Model
In The Illustrated Word2vec, we've looked at what a language model is -- basically a machine learning model that is able to look at part of a sentence and predict the next word. The most famous language models are smartphone keyboards that suggest the next word based on what you've currently typed.

In this sense, we can say that the GPT-2 is basically the next word prediction feature of a keyboard app, but one that is much larger and more sophisticated than what your phone has. The GPT-2 was trained on a massive 40GB dataset called WebText that the OpenAI researchers crawled from the internet as part of the research effort. To compare in terms of storage size, the keyboard app I use, SwiftKey, takes up 78MBs of space. The smallest variant of the trained GPT-2, takes up 500MBs of storage to store all of its parameters. The largest GPT-2 variant is 13 times the size so it could take up more than 6.5 GBs of storage space.

One great way to experiment with GPT-2 is using the AllenAI GPT-2 Explorer. It uses GPT-2 to display ten possible predictions for the next word (alongside their probability score). You can select a word then see the next list of predictions to continue writing the passage.
Transformers for Language Modeling

As we've seen in The Illustrated Transformer, the original transformer model is made up of an encoder and decoder -- each is a stack of what we can call transformer blocks. That architecture was appropriate because the model tackled machine translation -- a problem where encoder-decoder architectures have been successful in the past.

A lot of the subsequent research work saw the architecture shed either the encoder or decoder, and use just one stack of transformer blocks -- stacking them up as high as practically possible, feeding them massive amounts of training text, and throwing vast amounts of compute at them (hundreds of thousands of dollars to train some of these language models, likely millions in the case of AlphaStar).

How high can we stack up these blocks? It turns out that's one of the main distinguishing factors between the different GPT2 model sizes:

A robot may not injure a human being or, through inaction, allow a human being to come to harm.

The GPT-2 is built using transformer decoder blocks. BERT, on the other hand, uses transformer encoder blocks. We will examine the difference in a following section. But one key difference between the two is that GPT2, like traditional language models, outputs one token at a time. Let's for example prompt a well-trained GPT-2 to recite the first law of robotics:

The way these models actually work is that after each token is produced, that token is added to the sequence of inputs. And that new sequence becomes the input to the model in its next step. This is an idea called "auto-regression".
