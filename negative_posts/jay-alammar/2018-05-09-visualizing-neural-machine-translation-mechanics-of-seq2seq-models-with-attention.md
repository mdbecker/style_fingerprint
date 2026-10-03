---
source_type: technical_blog
author: Jay Alammar
author_id: jay-alammar
title: Visualizing A Neural Machine Translation Model (Mechanics of Seq2seq Models
  With Attention)
date: '2018-05-09'
source_url: https://jalammar.github.io/visualizing-neural-machine-translation-mechanics-of-seq2seq-models-with-attention/
download_url: https://raw.githubusercontent.com/jalammar/jalammar.github.io/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_posts/2018-05-09-visualizing-neural-machine-translation-mechanics-of-seq2seq-models-with-attention.md
repository_url: https://github.com/jalammar/jalammar.github.io
repository_revision: e4dbd4bb1cd3f05375d842b6c12f69ff37b01475
source_path: _posts/2018-05-09-visualizing-neural-machine-translation-mechanics-of-seq2seq-models-with-attention.md
license: CC-BY-NC-SA-4.0
license_url: https://creativecommons.org/licenses/by-nc-sa/4.0/
license_evidence_url: https://github.com/jalammar/jalammar.github.io/blob/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_layouts/default.html#L85
maximum_words: 400
retrieved_at: '2026-10-02T04:59:14.869357+00:00'
source_sha256: 9eaa4db9d12799aa43d6934e6ee02694c0e1fe00b1ace65e63004ddb5e62c28f
sample_sha256: c82cef8aa1fb770311f78f0b4e0e4a12212894f368e923f1c9453bb6aa7264f3
sampling: Contiguous sentence-complete prose excerpt, 150–400 whitespace words; markup/code/navigation/quoted
  blocks/equations removed.
excerpt_words: 390
excerpt: true
---

Watch: MIT's Deep Learning State of the Art lecture referencing this post

May 25th update: New graphics (RNN animation, word embedding graph), color coding, elaborated on the final attention example.

Note: The animations below are videos. Touch or hover on them (if you're using a mouse) to get play controls so you can pause if needed.

Sequence-to-sequence models are deep learning models that have achieved a lot of success in tasks like machine translation, text summarization, and image captioning. Google Translate started using such a model in production in late 2016. These models are explained in the two pioneering papers (Sutskever et al., 2014, Cho et al., 2014).

I found, however, that understanding the model well enough to implement it requires unraveling a series of concepts that build on top of each other. I thought that a bunch of these ideas would be more accessible if expressed visually. That's what I aim to do in this post. You'll need some previous understanding of deep learning to get through this post. I hope it can be a useful companion to reading the papers mentioned above (and the attention papers linked later in the post).

A sequence-to-sequence model is a model that takes a sequence of items (words, letters, features of an images...etc) and outputs another sequence of items. A trained model would work like this:

In neural machine translation, a sequence is a series of words, processed one after another. The output is, likewise, a series of words:

 Your browser does not support the video tag.
Looking under the hood

Under the hood, the model is composed of an encoder and a decoder.

The encoder processes each item in the input sequence, it compiles the information it captures into a vector (called the context). After processing the entire input sequence, the encoder sends the context over to the decoder, which begins producing the output sequence item by item.

The context is a vector (an array of numbers, basically) in the case of machine translation. The encoder and decoder tend to both be recurrent neural networks (Be sure to check out Luis Serrano's A friendly introduction to Recurrent Neural Networks for an intro to RNNs).

You can set the size of the context vector when you set up your model. It is basically the number of hidden units in the encoder RNN.
