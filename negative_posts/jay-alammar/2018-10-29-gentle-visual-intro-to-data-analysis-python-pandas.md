---
source_type: technical_blog
author: Jay Alammar
author_id: jay-alammar
title: A Gentle Visual Intro to Data Analysis in Python Using Pandas
date: '2018-10-29'
source_url: https://jalammar.github.io/gentle-visual-intro-to-data-analysis-python-pandas/
download_url: https://raw.githubusercontent.com/jalammar/jalammar.github.io/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_posts/2018-10-29-gentle-visual-intro-to-data-analysis-python-pandas.md
repository_url: https://github.com/jalammar/jalammar.github.io
repository_revision: e4dbd4bb1cd3f05375d842b6c12f69ff37b01475
source_path: _posts/2018-10-29-gentle-visual-intro-to-data-analysis-python-pandas.md
license: CC-BY-NC-SA-4.0
license_url: https://creativecommons.org/licenses/by-nc-sa/4.0/
license_evidence_url: https://github.com/jalammar/jalammar.github.io/blob/e4dbd4bb1cd3f05375d842b6c12f69ff37b01475/_layouts/default.html#L85
maximum_words: 350
retrieved_at: '2026-10-02T04:59:14.876217+00:00'
source_sha256: db0d43d899607a12eb50c75767b05269531dc9dad50e3362652af35570da07d3
sample_sha256: f3b350bfdbb352252156a5da4efece9467e0d09236ac345b049cd7edcef285e3
sampling: Contiguous sentence-complete prose excerpt, 150–350 whitespace words; markup/code/navigation/quoted
  blocks/equations removed.
excerpt_words: 345
excerpt: true
---

If you're planning to learn data analysis, machine learning, or data science tools in python, you're most likely going to be using the wonderful pandas library. Pandas is an open source library for data manipulation and analysis in python.
Loading Data
One of the easiest ways to think about that, is that you can load tables (and excel files) and then slice and dice them in multiple ways:

Pandas allows us to load a spreadsheet and manipulate it programmatically in python. The central concept in pandas is the type of object called a DataFrame -- basically a table of values which has a label for each row and column. Let's load this basic CSV file containing data from a music streaming service:

Now the variable is a pandas DataFrame:
Selection
We can select any column using its label:

We can select any slice of the table using a both column label and row numbers using (but here it would be inclusive of both bounding row numbers):

Now it gets more interesting. We can easily filter rows using the values of a specific row. For example, here are our jazz musicians:

Here are the artists who have more than 1,800,000 listeners:
Dealing with Missing Values

Many datasets you'll deal with in your data science journey will have missing values. Let's say our data frame has a missing value:

Pandas provides multiple ways to deal with this. The easiest is to just drop rows with missing values:

Another way would be to fill-in the missing value using (with 0, for example).
Grouping

Things start to get really interesting when you start grouping rows with certain criteria and aggregating their data. For example, let's group our dataset by genre and see how many listeners and plays each genre has:

Pandas grouped the the two "Jazz" rows into one, and since we used for aggregation, it added together the listeners and plays for the two Jazz artists and shows the sums in the combined Jazz column.

This is not only nifty, but is an extremely powerful data analysis method.
