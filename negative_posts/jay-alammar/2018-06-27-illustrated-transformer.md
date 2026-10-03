---
source_type: technical_blog
author: Jay Alammar
author_id: jay-alammar
title: The Illustrated Transformer
date: '2018-06-27'
source_url: https://jalammar.github.io/illustrated-transformer/
download_url: https://raw.githubusercontent.com/jalammar/jalammar.github.io/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_posts/2018-06-27-illustrated-transformer.md
repository_url: https://github.com/jalammar/jalammar.github.io
repository_revision: e4dbd4bb1cd3f05375d842b6c12f69ff37b01475
source_path: _posts/2018-06-27-illustrated-transformer.md
license: CC-BY-NC-SA-4.0
license_url: https://creativecommons.org/licenses/by-nc-sa/4.0/
license_evidence_url: https://github.com/jalammar/jalammar.github.io/blob/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_layouts/default.html#L85
maximum_words: 700
retrieved_at: '2026-10-02T04:59:14.874894+00:00'
source_sha256: e464366f35d0ce09d38d95d23c3ec0e04e0d64ddf9871a3b99b7eb126beb9861
sample_sha256: 77da4e4bfacceaafc7f270a24aa8114636e849645db7fce3a272adc183f59673
sampling: Contiguous sentence-complete prose excerpt, 150–700 whitespace words; markup/code/navigation/quoted
  blocks/equations removed.
excerpt_words: 697
excerpt: true
---

Watch: MIT's Deep Learning State of the Art lecture referencing this post

 Update: This post has now become a book! Check out LLM-book.com which contains (Chapter 3) an updated and expanded version of this post speaking about the latest Transformer models and how they've evolved in the seven years since the original Transformer (like Multi-Query Attention and RoPE Positional embeddings).

In the previous post, we looked at Attention -- a ubiquitous method in modern deep learning models. Attention is a concept that helped improve the performance of neural machine translation applications. In this post, we will look at The Transformer -- a model that uses attention to boost the speed with which these models can be trained. The Transformer outperforms the Google Neural Machine Translation model in specific tasks. The biggest benefit, however, comes from how The Transformer lends itself to parallelization. It is in fact Google Cloud's recommendation to use The Transformer as a reference model to use their Cloud TPU offering. So let's try to break the model apart and look at how it functions.

The Transformer was proposed in the paper Attention is All You Need. A TensorFlow implementation of it is available as a part of the Tensor2Tensor package. Harvard's NLP group created a guide annotating the paper with PyTorch implementation. In this post, we will attempt to oversimplify things a bit and introduce the concepts one by one to hopefully make it easier to understand to people without in-depth knowledge of the subject matter.

2025 Update: We've built a free short course that brings the contents of this post up-to-date with animations:

A High-Level Look
Let's begin by looking at the model as a single black box. In a machine translation application, it would take a sentence in one language, and output its translation in another.

Popping open that Optimus Prime goodness, we see an encoding component, a decoding component, and connections between them.

The encoding component is a stack of encoders (the paper stacks six of them on top of each other -- there's nothing magical about the number six, one can definitely experiment with other arrangements). The decoding component is a stack of decoders of the same number.

The encoders are all identical in structure (yet they do not share weights). Each one is broken down into two sub-layers:

The encoder's inputs first flow through a self-attention layer -- a layer that helps the encoder look at other words in the input sentence as it encodes a specific word. We'll look closer at self-attention later in the post.

The outputs of the self-attention layer are fed to a feed-forward neural network. The exact same feed-forward network is independently applied to each position.

The decoder has both those layers, but between them is an attention layer that helps the decoder focus on relevant parts of the input sentence (similar what attention does in seq2seq models).

Now that we've seen the major components of the model, let's start to look at the various vectors/tensors and how they flow between these components to turn the input of a trained model into an output.

As is the case in NLP applications in general, we begin by turning each input word into a vector using an embedding algorithm.

 Each word is embedded into a vector of size 512. We'll represent those vectors with these simple boxes.

The embedding only happens in the bottom-most encoder. The abstraction that is common to all the encoders is that they receive a list of vectors each of the size 512 -- In the bottom encoder that would be the word embeddings, but in other encoders, it would be the output of the encoder that's directly below. The size of this list is hyperparameter we can set -- basically it would be the length of the longest sentence in our training dataset.

After embedding the words in our input sequence, each of them flows through each of the two layers of the encoder.

Here we begin to see one key property of the Transformer, which is that the word in each position flows through its own path in the encoder. There are dependencies between these paths in the self-attention layer.
