---
author: Jay Alammar
author_id: jay-alammar
title: A Visual and Interactive Guide to the Basics of Neural Networks
date: '2016-12-14'
source_url: https://jalammar.github.io/visual-interactive-guide-basics-neural-networks/
download_url: https://raw.githubusercontent.com/jalammar/jalammar.github.io/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_posts/2016-12-14-visual-interactive-guide-basics-neural-networks.md
repository_url: https://github.com/jalammar/jalammar.github.io
repository_revision: e4dbd4bb1cd3f05375d842b6c12f69ff37b01475
source_path: _posts/2016-12-14-visual-interactive-guide-basics-neural-networks.md
license: CC-BY-NC-SA-4.0
license_url: https://creativecommons.org/licenses/by-nc-sa/4.0/
license_evidence_url: https://github.com/jalammar/jalammar.github.io/blob/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_layouts/default.html#L85
maximum_words: 250
retrieved_at: '2026-10-02T04:59:14.867069+00:00'
source_sha256: 986c850a5a1daa5374e07b602efda8b6933f806afc87a25c99c696415c3a3cc1
sample_sha256: 8ddae02bc2898be38dba4763099fe848982087947ba3e1426c29a1a97ea2bf66
sampling: Contiguous sentence-complete prose excerpt, 150–250 whitespace words; markup/code/navigation/quoted
  blocks/equations removed.
excerpt_words: 249
excerpt: true
---

So I started learning what I can about the basics of the topic, and saw the need for gentler resources for people with no experience in the field. This is my attempt at that.

Start here
Let's start with a simple example. Say you're helping a friend who wants to buy a house. She was quoted $400,000 for a 2000 sq ft house (185 meters). Is this a good price or not?

It's not easy to tell without a frame of reference. So you ask your friends who have bought houses in that same neighborhoods, and you end up with three data points:

 | Area (sq ft) (x) | Price (y) |
 | --- | --- |
 | 2,104 | 399,900 |
 | 1,600 | 329,900 |
 | 2,400 | 369,000 |

Personally, my first instinct would be to get the average price per sq ft. That comes to $180 per sq ft.

Welcome to your first neural network! Now it's not quite at Siri level yet, but now you know the fundamental building block. And it looks like this:

Diagrams like this show you the structure of the network and how it calculates a prediction. The calculation starts from the input node at the left. The input value flows to the right. It gets multiplied by the weight and the result becomes our output.

Multiplying 2,000 sq ft by 180 gives us $360,000. That's all there is to it at this level. Calculating the prediction is simple multiplication.
