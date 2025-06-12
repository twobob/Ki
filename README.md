# Ki


![SCREENSHOT](https://raw.githubusercontent.com/twobob/Ki/master/2ColumnScreenshot.JPG "Screenshot of example implementation")

__Use python and other free bits to create the files required to make an Elasticlunr.js searchable image tag website__

This repository is a slightly modified example of Elasticlunr.js. It uses a fully local BLIP‑2 captioning approach to tag images.
It should "just work" to give you a working thing to throw at a webserver.

The additional utilty scripts below should give you enough info to populate the model with stuff (thumbs that are logically linked to the data.JSON) of your own.  

### NOTES ON Supporting Documents 
The scripts assume Windows OS since the unixers out there can probably bash up their own in short order.

We optionally use __ImageMagick__ as __Magick.exe__ and __Jpeg-compress.exe__ command line utilities since they are free and Windows-friendly. Replace with your weapon of choice. You could do this stuff in the old CS2 version of Photoshop with a single batch command.
Anything really.  

Python is used to provide a relatively cross-platform overview of the steps needed, please amend directory separators and paths to something sensible.  

### TODO/MAYBES: 
* ~~FIX THE BROKEN LAYOUT ON SLIM SCREENS~~ Done
* Make the partial rendering loop stop when you click a result before it is finished
* Add transactional folders such as IN - PROCESSED - ERROR to allow for more efficent addition of new content
* Check the EXIF/File attrs for Time Created and use that to compare against a stored "last sync" date for previous point
* ~~app.inputs.bulk_create_images(images)  rather than loop over a single call.~~ If we implement training. maybe.
* Maybe just roll all the scripts in python examples
* Import the scripts, after a tidy up, to the repo in the interim
* Add a script that searches network drives and looks in areas that phones are likely to sync to.
* Maybe centralise the JSON and offer a "single JSON Blob" option to reduce .txt file clutter
* Do some corner case testing, yeah, some testing at all really...
* ~~Update this repo to the latest 2 column layout with all the fixes~~ Done

## Supporting Documents and scripts

Here is a short sequence of reasonably accurate (and hastily slapped together) scripts to create a text driven image search engine.
Time taken so far is only a few hours of actual coding and testing.  

__offline_tags.py__
Walk over JPG files and create single-word tag files using the open-source BLIP‑2 model and spaCy.
Runs entirely offline with no external dependencies.

`python offline_tags.py PATH_TO_IMAGES`

__processing batches__
You can run `offline_tags.py` over large folders or in batches as needed. Each image
produces a `.txt` file containing the extracted tags.

__unify the txt's to JSON__
Then create a single unified JSON file from the generated `.txt` tag files
<https://gist.github.com/twobob/dad0a110b0c2b2eb4895d8e6e5e76760>
_(You could also store the raw caption results if you prefer; this two-stage process keeps the data blob tidy.)_

we minified that output eventually, when testing was complete.

Next process the images
use ImageMagick command line on Windows to make source images as unrotated as possible (Caveat emptor, YMMV)
<https://gist.github.com/twobob/38e796de3aa42b2fd7d296394f3c9279>
_this is helpful for making meaningful thumbnails later, uses EXIF to unrotate)_  

Now, make thumbs for web purposes and eventual display of the images
<https://gist.github.com/twobob/f5dd8a25195d730801df25bf048c3272>
_(We chose 240x240 in the end, it scales nicely to 480, which is plenty for previews, not the 128x128 in the title)_

`make_thumbs.py` automates this step using Python and Pillow. Run
`python make_thumbs.py PATH_TO_IMAGES` to generate oriented thumbnails in a
`thumbs` subfolder. A `thumbs/overlay/watermark.png` file can be used as an
optional watermark.

Since this is web facing we are all about size with thousands of files to serve,
so we crunch the THUMB.JPG files in /thumbs with jpeg-recompress.exe
__cmd one liner__  <https://gist.github.com/twobob/e10bb9163a6fc715be28610be58b5d8b>
_this gets us pretty decent images for as little as 10-30kb depending on content, you could crush harder.
our 7GB of images are now about 40Mb_

### Next up we get a tiny search engine - we used elasticlunr.js

They have a fully working example online here that we will modify
<http://elasticlunr.com/example/index.html>  

Rework the index.html to have less clutter and not require so much typing
<https://gist.github.com/twobob/85428a92477e7cbd3eb50a6652f27d60>  

We adjust the app.js to use handlebars.js over the older mustache.js in the demo - (download the code from a cdn, make it local)
We add incremental rendering and limited index config to get decent loading times for 2000 results
The word list view now updates dynamically since `renderWordList` uses its parameter.
<https://gist.github.com/twobob/82e2c9a628e50d5cf81f41a9a44e27f2>
_(loading 50 thumbs at a time with progress indication)_

Please __DO__ consider the file endings' CASE SENSITIVITY to .JPG not .jpg  
(although pretty sure that is corner-case covered in the scripts IIRC, J.I.C.)  

Hope this helps someone realise the power of AI tagging and a tiny Luceney, Elasticsearch style search indexing.

### Running the site locally

The generated HTML files can be served with Python's built-in web server.
From the repository folder run one of the following commands:

 - **Linux:** `python3 serve.py`
 - **Windows:** `python serve.py`

This will host the site at <http://localhost:8000>.

#### LICENSE

I claim no ownership of these and they were cobbled together from public domain code or mangled together by me. For my sins. 
Again, I take no credit. My pedagogical employer wanted one of these. There went the bank holiday w/e ;)  

I release this under a "do what you want but dont sue me or anyone I know" license.  
Or some other more legal one that is similar. suggestions politely accepted.  
  
