---
author: Jay Alammar
author_id: jay-alammar
title: A Visual Guide to Using BERT for the First Time
date: '2019-11-26'
source_url: https://jalammar.github.io/a-visual-guide-to-using-bert-for-the-first-time/
download_url: https://raw.githubusercontent.com/jalammar/jalammar.github.io/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_posts/2019-11-26-a-visual-guide-to-using-bert-for-the-first-time.md
repository_url: https://github.com/jalammar/jalammar.github.io
repository_revision: e4dbd4bb1cd3f05375d842b6c12f69ff37b01475
source_path: _posts/2019-11-26-a-visual-guide-to-using-bert-for-the-first-time.md
license: CC-BY-NC-SA-4.0
license_url: https://creativecommons.org/licenses/by-nc-sa/4.0/
license_evidence_url: https://github.com/jalammar/jalammar.github.io/blob/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_layouts/default.html#L85
maximum_words: 500
retrieved_at: '2026-10-02T04:59:14.901362+00:00'
source_sha256: 19c991ebef744a7932f01d486a673a16d04ed2fe765d112af405d9a25f374034
sample_sha256: d022a9ca9845c5aeac1b1a21718ba137ac59c29155c12ff2fd0698f7c65d4b17
sampling: Contiguous sentence-complete prose excerpt, 150–500 whitespace words; markup/code/navigation/quoted
  blocks/equations removed.
excerpt_words: 492
excerpt: true
---

Progress has been rapidly accelerating in machine learning models that process language over the last couple of years. This progress has left the research lab and started powering some of the leading digital products. A great example of this is the recent announcement of how the BERT model is now a major force behind Google Search. Google believes this step (or progress in natural language understanding as applied in search) represents "the biggest leap forward in the past five years, and one of the biggest leaps forward in the history of Search".

This post is a simple tutorial for how to use a variant of BERT to classify sentences. This is an example that is basic enough as a first intro, yet advanced enough to showcase some of the key concepts involved.

Alongside this post, I've prepared a notebook. You can see it here the notebook or run it on colab.
Dataset: SST2
The dataset we will use in this example is SST2, which contains sentences from movie reviews, each labeled as either positive (has the value 1) or negative (has the value 0):

Models: Sentence Sentiment Classification
Our goal is to create a model that takes a sentence (just like the ones in our dataset) and produces either 1 (indicating the sentence carries a positive sentiment) or a 0 (indicating the sentence carries a negative sentiment). We can think of it as looking like this:

Under the hood, the model is actually made up of two model.
DistilBERT processes the sentence and passes along some information it extracted from it on to the next model. DistilBERT is a smaller version of BERT developed and open sourced by the team at HuggingFace. It's a lighter and faster version of BERT that roughly matches its performance.
The next model, a basic Logistic Regression model from scikit learn will take in the result of DistilBERT's processing, and classify the sentence as either positive or negative (1 or 0, respectively).

 The data we pass between the two models is a vector of size 768. We can think of this of vector as an embedding for the sentence that we can use for classification.

If you've read my previous post, Illustrated BERT, this vector is the result of the first position (which receives the [CLS] token as input).
Model Training
While we'll be using two models, we will only train the logistic regression model. For DistillBERT, we'll use a model that's already pre-trained and has a grasp on the English language. This model, however is neither trained not fine-tuned to do sentence classification. We get some sentence classification capability, however, from the general objectives BERT is trained on. This is especially the case with BERT's output for the first position (associated with the [CLS] token). I believe that's due to BERT's second training object -- Next sentence classification. That objective seemingly trains the model to encapsulate a sentence-wide sense to the output at the first position.
