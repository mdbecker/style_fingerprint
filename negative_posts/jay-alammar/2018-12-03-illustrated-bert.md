---
source_type: technical_blog
author: Jay Alammar
author_id: jay-alammar
title: The Illustrated BERT, ELMo, and co. (How NLP Cracked Transfer Learning)
date: '2018-12-03'
source_url: https://jalammar.github.io/illustrated-bert/
download_url: https://raw.githubusercontent.com/jalammar/jalammar.github.io/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_posts/2018-12-03-illustrated-bert.md
repository_url: https://github.com/jalammar/jalammar.github.io
repository_revision: e4dbd4bb1cd3f05375d842b6c12f69ff37b01475
source_path: _posts/2018-12-03-illustrated-bert.md
license: CC-BY-NC-SA-4.0
license_url: https://creativecommons.org/licenses/by-nc-sa/4.0/
license_evidence_url: https://github.com/jalammar/jalammar.github.io/blob/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_layouts/default.html#L85
maximum_words: 600
retrieved_at: '2026-10-02T04:59:14.879828+00:00'
source_sha256: 3a122025dc054c57457b6873420093dd9f8f491939dc1ed1e52b59ce6cb44a8f
sample_sha256: a3f6953576733aa0b83f24bfcab8c86c046537fde56b81d02ed168a118831884
sampling: Contiguous sentence-complete prose excerpt, 150–600 whitespace words; markup/code/navigation/quoted
  blocks/equations removed.
excerpt_words: 567
excerpt: true
---

2021 Update: I created this brief and highly accessible video intro to BERT

The year 2018 has been an inflection point for machine learning models handling text (or more accurately, Natural Language Processing or NLP for short). Our conceptual understanding of how best to represent words and sentences in a way that best captures underlying meanings and relationships is rapidly evolving. Moreover, the NLP community has been putting forward incredibly powerful components that you can freely download and use in your own models and pipelines (It's been referred to as NLP's ImageNet moment, referencing how years ago similar developments accelerated the development of machine learning in Computer Vision tasks).

(ULM-FiT has nothing to do with Cookie Monster. But I couldn't think of anything else..)

One of the latest milestones in this development is the release of BERT, an event described as marking the beginning of a new era in NLP. BERT is a model that broke several records for how well models can handle language-based tasks. Soon after the release of the paper describing the model, the team also open-sourced the code of the model, and made available for download versions of the model that were already pre-trained on massive datasets. This is a momentous development since it enables anyone building a machine learning model involving language processing to use this powerhouse as a readily-available component -- saving the time, energy, knowledge, and resources that would have gone to training a language-processing model from scratch.

 The two steps of how BERT is developed. You can download the model pre-trained in step 1 (trained on un-annotated data), and only worry about fine-tuning it for step 2. [Source for book icon].

BERT builds on top of a number of clever ideas that have been bubbling up in the NLP community recently -- including but not limited to Semi-supervised Sequence Learning (by Andrew Dai and Quoc Le), ELMo (by Matthew Peters and researchers from AI2 and UW CSE), ULMFiT (by fast.ai founder Jeremy Howard and Sebastian Ruder), the OpenAI transformer (by OpenAI researchers Radford, Narasimhan, Salimans, and Sutskever), and the Transformer (Vaswani et al).

There are a number of concepts one needs to be aware of to properly wrap one's head around what BERT is. So let's start by looking at ways you can use BERT before looking at the concepts involved in the model itself.
Example: Sentence Classification
The most straight-forward way to use BERT is to use it to classify a single piece of text. This model would look like this:

To train such a model, you mainly have to train the classifier, with minimal changes happening to the BERT model during the training phase. This training process is called Fine-Tuning, and has roots in Semi-supervised Sequence Learning and ULMFiT.

For people not versed in the topic, since we're talking about classifiers, then we are in the supervised-learning domain of machine learning. Which would mean we need a labeled dataset to train such a model. For this spam classifier example, the labeled dataset would be a list of email messages and a label ("spam" or "not spam" for each message).

Other examples for such a use-case include:
Sentiment analysis
Input: Movie/Product review. Output: is the review positive or negative?
Example dataset: SST
Fact-checking
Input: sentence. Output: "Claim" or "Not Claim"
More ambitious/futuristic example:
Full Fact is an organization building automatic fact-checking tools for the benefit of the public.
