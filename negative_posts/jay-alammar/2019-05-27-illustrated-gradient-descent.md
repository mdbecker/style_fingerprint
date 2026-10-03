---
source_type: technical_blog
author: Jay Alammar
author_id: jay-alammar
title: How Machines Learn (The Illustrated Gradient Descent)
date: '2019-05-27'
source_url: https://jalammar.github.io/illustrated-gradient-descent/
download_url: https://raw.githubusercontent.com/jalammar/jalammar.github.io/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_posts/2019-05-27-illustrated-gradient-descent.md
repository_url: https://github.com/jalammar/jalammar.github.io
repository_revision: e4dbd4bb1cd3f05375d842b6c12f69ff37b01475
source_path: _posts/2019-05-27-illustrated-gradient-descent.md
license: CC-BY-NC-SA-4.0
license_url: https://creativecommons.org/licenses/by-nc-sa/4.0/
license_evidence_url: https://github.com/jalammar/jalammar.github.io/blob/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_layouts/default.html#L85
maximum_words: 300
retrieved_at: '2026-10-02T04:59:14.889989+00:00'
source_sha256: 0383a1eb2de4e6c3be2d14525a9d8996183569787db947b997cc2f5ce5e0d70e
sample_sha256: d5e13648a9b3c0eeb0f7319b2763b59cc5be4a30d750fe0e9a9115ed278344be
sampling: Contiguous sentence-complete prose excerpt, 150–300 whitespace words; markup/code/navigation/quoted
  blocks/equations removed.
excerpt_words: 266
excerpt: true
---

At a time when a lot of people are trying to learn machine learning to improve their careers or satisfy their curiosity, I feel there's still a lot that can be done to improve how accessible this body of knowledge is to outsiders. Nowhere is this more evident than in the "learning" concept of machine learning (neural networks in particular). A concept shrouded in mystery forcing non-specialists to speak of it in handwavy terms. The leading "learning" concept in neural networks is an algorithm called Gradient Descent.

The second post I wrote in this blog sets the stage for this post by showing how a simple prediction is calculated and how we evaluate models (by calculating error/loss). It leads you right up to the curtain of Gradient Descent and how it can rapidly improve the accuracy of a prediction model. In this post we'll start with a simpler example then peer through that curtain. It would be beneficial if you read that post first.
But First, Ice Cream!
If a group of three people walk into an ice cream shop, how much do you think they'll end up paying?

This is a type of question where the only possible answer is "it depends". We don't have a formula for this type of broad question. We can, however, make a reasonable guess if we looked at the sales records of that shop:

By looking at this dataset, can you predict how much this group of three people would pay? Your prediction doesn't need to be 100% accurate, just the best estimate given the data that we have.
