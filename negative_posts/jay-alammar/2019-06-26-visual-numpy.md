---
source_type: technical_blog
author: Jay Alammar
author_id: jay-alammar
title: A Visual Intro to NumPy and Data Representation
date: '2019-06-26'
source_url: https://jalammar.github.io/visual-numpy/
download_url: https://raw.githubusercontent.com/jalammar/jalammar.github.io/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_posts/2019-06-26-visual-numpy.md
repository_url: https://github.com/jalammar/jalammar.github.io
repository_revision: e4dbd4bb1cd3f05375d842b6c12f69ff37b01475
source_path: _posts/2019-06-26-visual-numpy.md
license: CC-BY-NC-SA-4.0
license_url: https://creativecommons.org/licenses/by-nc-sa/4.0/
license_evidence_url: https://github.com/jalammar/jalammar.github.io/blob/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_layouts/default.html#L85
maximum_words: 450
retrieved_at: '2026-10-02T04:59:14.892642+00:00'
source_sha256: c52aa4f538ed7e25fe2874809bc68f79511bef57abccdb452e923bbf1b2c40f3
sample_sha256: 90f898d8a55de2949f63471efca92e538609b5c9429d8b9ac05c30bfa872e866
sampling: Contiguous sentence-complete prose excerpt, 150–450 whitespace words; markup/code/navigation/quoted
  blocks/equations removed.
excerpt_words: 444
excerpt: true
---

The NumPy package is the workhorse of data analysis, machine learning, and scientific computing in the python ecosystem. It vastly simplifies manipulating and crunching vectors and matrices. Some of python's leading package rely on NumPy as a fundamental piece of their infrastructure (examples include scikit-learn, SciPy, pandas, and tensorflow). Beyond the ability to slice and dice numeric data, mastering numpy will give you an edge when dealing and debugging with advanced usecases in these libraries.

In this post, we'll look at some of the main ways to use NumPy and how it can represent different types of data (tables, images, text...etc) before we can serve them to machine learning models.

We can create a NumPy array (a.k.a. the mighty ndarray) by passing a python list to it and using . In this case, python creates the array we can see on the right here:

There are often cases when we want NumPy to initialize the values of the array for us. NumPy provides methods like ones(), zeros(), and random.random() for these cases. We just pass them the number of elements we want it to generate:

Once we've created our arrays, we can start to manipulate them in interesting ways.
Array Arithmetic
Let's create two NumPy arrays to showcase their usefulness. We'll call them and :

Adding them up position-wise (i.e. adding the values of each row) is as simple as typing :

When I started learning such tools, I found it refreshing that an abstraction like this makes me not have to program such a calculation in loops. It's a wonderful abstraction that allows you to think about problems at a higher level.

There are often cases when we want to carry out an operation between an array and a single number (we can also call this an operation between a vector and a scalar). Say, for example, our array represents distance in miles, and we want to convert it to kilometers. We simply say :

See how NumPy understood that operation to mean that the multiplication should happen with each cell? That concept is called broadcasting, and it's very useful.
Indexing

We can index and slice NumPy arrays in all the ways we can slice python lists:

In addition to , , and , you get all the greats like to get the average, to get the result of multiplying all the elements together, to get standard deviation, and plenty of others.
In more dimensions

All the examples we've looked at deal with vectors in one dimension. A key part of the beauty of NumPy is its ability to apply everything we've looked at so far to any number of dimensions.
Creating Matrices
