---
source_type: technical_blog
author: Jay Alammar
author_id: jay-alammar
title: The Illustrated Word2vec
date: '2019-03-27'
source_url: https://jalammar.github.io/illustrated-word2vec/
download_url: https://raw.githubusercontent.com/jalammar/jalammar.github.io/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_posts/2019-03-27-illustrated-word2vec.md
repository_url: https://github.com/jalammar/jalammar.github.io
repository_revision: e4dbd4bb1cd3f05375d842b6c12f69ff37b01475
source_path: _posts/2019-03-27-illustrated-word2vec.md
license: CC-BY-NC-SA-4.0
license_url: https://creativecommons.org/licenses/by-nc-sa/4.0/
license_evidence_url: https://github.com/jalammar/jalammar.github.io/blob/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_layouts/default.html#L85
maximum_words: 500
retrieved_at: '2026-10-02T04:59:14.886106+00:00'
source_sha256: 55d336587bca04cb301d65454c955105b4118880f82ff18968bdd1a74133d2f0
sample_sha256: ef905574ff4551e1b90781d05b844430bc3caad5828478eccb886ffb4b2d0134
sampling: Contiguous sentence-complete prose excerpt, 150–500 whitespace words; markup/code/navigation/quoted
  blocks/equations removed.
excerpt_words: 499
excerpt: true
---

“There is in all things a pattern that is part of our universe. It has symmetry, elegance, and grace - those qualities you find always in that which the true artist captures. You can find it in the turning of the seasons, in the way sand trails along a ridge, in the branch clusters of the creosote
 bush or the pattern of its leaves.

 We try to copy these patterns in our lives and our society,
 seeking the rhythms, the dances, the forms that comfort.
 Yet, it is possible to see peril in the finding of
 ultimate perfection. It is clear that the ultimate
 pattern contains it own fixity. In such
 perfection, all things move toward death.”
 ~ Dune (1965)

I find the concept of embeddings to be one of the most fascinating ideas in machine learning. If you've ever used Siri, Google Assistant, Alexa, Google Translate, or even smartphone keyboard with next-word prediction, then chances are you've benefitted from this idea that has become central to Natural Language Processing models. There has been quite a development over the last couple of decades in using embeddings for neural models (Recent developments include contextualized word embeddings leading to cutting-edge models like BERT and GPT2).

Word2vec is a method to efficiently create word embeddings and has been around since 2013. But in addition to its utility as a word-embedding method, some of its concepts have been shown to be effective in creating recommendation engines and making sense of sequential data even in commercial, non-language tasks. Companies like Airbnb, Alibaba, Spotify, and Anghami have all benefitted from carving out this brilliant piece of machinery from the world of NLP and using it in production to empower a new breed of recommendation engines.

In this post, we'll go over the concept of embedding, and the mechanics of generating embeddings with word2vec. But let's start with an example to get familiar with using vectors to represent things. Did you know that a list of five numbers (a vector) can represent so much about your personality?
Personality Embeddings: What are you like?

“I give you the desert chameleon, whose ability to blend itself into the background tells you all you need to know about the roots of ecology and the foundations of a personal identity” ~Children of Dune

On a scale of 0 to 100, how introverted/extraverted are you (where 0 is the most introverted, and 100 is the most extraverted)?
Have you ever taken a personality test like MBTI -- or even better, the Big Five Personality Traits test? If you haven't, these are tests that ask you a list of questions, then score you on a number of axes, introversion/extraversion being one of them.

 Example of the result of a Big Five Personality Trait test. It can really tell you a lot about yourself and is shown to have predictive ability in academic, personal, and professional success. This is one place to find your results.

Imagine I've scored 38/100 as my introversion/extraversion score.
