# Ki

![SCREENSHOT](https://ibin.co/w800/3LDwKlGSsulY.png "Screenshot of example implementation")

__Use python and other free bits to create the files required to make an Elasticlunr.js searchable image tag website__

This repos is a slightly modified example of Elasticlunr.js to demonstrate the a usage for the Clarifai API
it should "just work" to give you a working thing to throw at a webserver

The additional utilty scripts below should give you enough info to populate the model with stuff (thumbs that are logically linked to the data.JSON) of your own.  

The scripts assume windows since the unixers out there can probably bash up their own in short order.

We optionally use __ImageMagick__ as __Magick.exe__ and __Jpeg-compress.exe__ command line utilities since they are free and Windows-friendly. Replace with your weapon of choice. You could do this stuff in the old CS2 version of Photoshop with a single batch command.
Anything really.

Python is used to provide a relatively cross platform overview of the steps needed, please amend directory spearators and paths to something sensible.

### TODO/MAYBES: 
Maybe just roll all the scripts in python examples
Import the scripts, after a tidy up, to the repo in the interim
Add a script that searches network drives and looks in areas that phones are likely to sync to.
Maybe centralise the JSON and offer a "single JSON Blob" switch for claripy.py reducing .txt file clutter
Do some corner case testing, yeah, some testing at all really...

## Supporting Documents and scripts

Here is a short sequence of reasonably accurate (and hastily slapped together) scripts to create a text driven image search engine.
Time taken so far is only a few hours of actual coding and testing.

__claripy.py__
walk over JPG files and create human readable output of the tagging values in one .txt file for each image via the Clarifai API using Python on Windows

<https://gist.github.com/twobob/241511cea52e19da42ce99c5934f9d04>
_(You could of course store the json, we wanted something legible in this stage)_

__looping the claripy__
I batched 100 images by running ten loops at a time using
<https://gist.github.com/twobob/03a6a00f757b0ff8733b10e822b4e8cc>

```for /L %a in (1,1,10) do (python.exe claripy.py && timeout 5 >nul)
```
_With 10 images in the claripy.py document, you could do the 32 recommended images if you preferred.
This way gave nice, regular visually parsable output on the command line,  We processed circa 2000 images.
Clarifai's free monthy plan allows for 5000 ops (so you can get it horribly wrong once with 2k, lol)_

__unify the txt's to JSON__
Then create a single unified JSON file from a list of txt files parsing the values
<https://gist.github.com/twobob/dad0a110b0c2b2eb4895d8e6e5e76760>
_(You could just store the original claripy 'results' value and walk over that, we preferred this two stage process for greater control of the resulting data blob )_

we minified that output eventually, when testing was complete

Next process the images
use ImageMagick command line on Windows to make source images as unrotated as possible (Caveat emptor, YMMV)
<https://gist.github.com/twobob/38e796de3aa42b2fd7d296394f3c9279>
_this is helpful for making meaningful thumbnails later, uses EXIF to unrotate)_

Now, make thumbs for web purposes and eventual display of the images
<https://gist.github.com/twobob/f5dd8a25195d730801df25bf048c3272>
_(We chose 240x240 in the end, it scales nicely to 480, which is plenty for previews, not the 128x128 in the title)_

since this is web facing we are all about size with thousands of files to serve so we crunch the THUMB.JPG files in /thumbs with jpeg-recompress.exe
__cmd one liner__  <https://gist.github.com/twobob/e10bb9163a6fc715be28610be58b5d8b>
_this gets us pretty decent images for as little as 10-30kb depending on content, you could crush harder.
our 7GB of images are now about 40Mb_

### Next up we get a tiny search engine - we used elasticlunr.js

They have a fully working example online here that we will modify
<http://elasticlunr.com/example/index.html>

we rework the index.html to have less clutter and not require so much typing
<https://gist.github.com/twobob/85428a92477e7cbd3eb50a6652f27d60>

we adjust the app.js to use handlebars.js over the older mustache.js in the demo - (download the code from a cdn, make it local)
we add incremental rendering and limited index config to get decent loading times for 2000 results 
<https://gist.github.com/twobob/82e2c9a628e50d5cf81f41a9a44e27f2>
_(loading 50 thumbs at a time with progress indication)_

Please do consider the file endings CASE SENSITIVITY to .JPG not .jpg  (although pretty sure that is covered in the scripts, J.I.C.)

Hope this helps someone realise the power of AI tagging and tiny lucene, Elastic style search indexing.

#### LICENSE

I claim no ownership of these and they were cobbled together from public domain code or mangled together by be.
Again, I take no credit. My pedagogical employer wanted one of these. There went the bank holiday w/e ;)

I release this under a "do what you want but dont sue me or anyone I know" license.
Or some other more legal one that is similar. suggestions politey accepted.

