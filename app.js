requirejs.config({waitSeconds:0});
require([
  './jquery.js',
  './handlebars.min.js',
  './elasticlunr.min.js',
  'text!templates/question_view.mustache',
  'text!templates/question_list.mustache',
   'text!templates/word_list.mustache',
  'text!data.json'
], function (_, Mustache, elasticlunr, questionView, questionList, wordList, data, indexDump) {

//,  'text!example_index.json',   'text!example_data.json', 

var WLtemplate = Mustache.compile(wordList);
var QLtemplate = Mustache.compile(questionList);
var QVtemplate = Mustache.compile(questionView);
	
var seeder = 11091974;

var BodyRef = document.getElementById("body");
var clearButton =   $('#clearButton');

  var renderQuestionList = function (qs) {
    $("#question-list-container")
      .empty()
	  .append(QLtemplate({questions: qs}));
  }
 
    var renderWordList = function (qs) {

    $("#question-list-container")
      .empty()
      .append(WLtemplate({list: qs}));
  }

  var renderQuestionView = function (question) {
    $("#question-view-container")
      .empty()
      .append(QVtemplate(question));
  
  }

  window.profile = function (term) {
    console.profile('search');
    window.idx.search(term);
    console.profileEnd('search');
  }

  window.search = function (term) {
    console.time('search')
    idx.search(term)
    console.timeEnd('search')
  }


   var idx = elasticlunr(function () {
	this.setRef('id');
    this.addField('title');
	this.addField('searchTerms');
	this.addField('tags');
	this.saveDocument(false);
});
 
 Mustache.registerHelper('everyOther', function (index, options) {
   if(index%2 == 0){
            return options.fn(this);
       } else {
            return options.inverse(this);
         }
 
});
 
  // Modified to 
  Array.prototype.byCount= function(){
	//var lenHolder = [];
    var itm, a= [], L= this.length, o= {};
    for(var i= 0; i<L; i++){
        itm= this[i];
        if(!itm) continue;
        if(o[itm]== undefined) o[itm]= 1;
        else ++o[itm];
    }
	countHolder = []; 
    for(var p in o) {a[a.length]= p; 	
	countHolder[countHolder.length] = { name: a.slice(-1).toString() , amount: o[p]};
	}
	var returnWithCounts = 
	a.sort(function(a, b){
        return o[b]-o[a];
    })
	countHolder.sort(function(a, b){
        return a.amount >b.amount;
    })
    return returnWithCounts };
 
 // prep the questions
 var fulllist = [];
 var rawQuestions = JSON.parse(data).questions;
 
 rawQuestions.map(function (raw) {
 for (thing in raw.question.content )
	{
	fulllist[fulllist.length]= thing; //{'x': thing};
	}
})
  
 var shortlist = fulllist.byCount();
	dict = {}
	countHolder.forEach(function(x) {
    dict[x.name] = x.amount
	})
 
 
  var questions = rawQuestions.map(function (raw) {
	  rawQuestion = raw;
	  
	  var holder = ""	  
	  for (i in raw.question.content){
		 holder +=i +' : '+ raw.question.content[i]+'\n';
		}
	var make_id =   murmurhash3_32_gc(raw.img.filename, seeder); 
	//console.log(make_id);

	var clickableTags = Object.keys(raw.question.content).map(function (k) {
		
		var result = '<a title="'+dict[k]+' results for '+k+  '" style="cursor:pointer" onclick="searchTerm(\''+k+'\')">'+k+'</a>';	
		
		return result;
	})
	
	
    return {
		
      id: make_id,
      title:  raw.img.filename.replace('.JPG',''),
      body: holder,
	  searchTerms: Object.keys(raw.question.content).join(' '),
      tags:  clickableTags, // Object.keys(raw.question.content).join(' '),
	  img: raw.img.filename,
	  thumb: raw.thumb.filename
    }
  })

  
  questions.forEach(function (question) {
    idx.addDoc(question);
  });
  
  
window.idx = idx;

  var config = '{    "fields": {        "searchTerms": {"boost": 2},      "title": {"boost": 1}    },   "boolean": "AND"}';
  var json_config = new elasticlunr.Configuration(config, window.idx.getFields()).get();

document.getElementById("loader").style.display = "none" ;
document.getElementById("hiding_title").style.display = "none" ;

  renderQuestionView(questions[0])

  

shortlist = countHolder.map(function (raw) { return { x : raw.name, count: raw.amount }	}); 



	 var emptyFunction = function emptyMe (){
	  
	   $('input').val('');
	  renderWordList(shortlist);
  }
window.emptyFunction = emptyFunction;
	
  renderWordList(shortlist);
	

  var debounce = function (fn) {
    var timeout
    return function () {
      var args = Array.prototype.slice.call(arguments),
          ctx = this

      clearTimeout(timeout)
      timeout = setTimeout(function () {
        fn.apply(ctx, args)
      }, 100)
    }
  }


  
   var  renderPartialQuestionList = function (results, startPos, endPos){
	  var temp = results.slice(startPos, endPos);
	     $("#question-list-container")
	  .append(QLtemplate({questions: temp}))
  }
  
  function doHeavyWork(results, start, totalResultsToRender, term) {
    var total = totalResultsToRender;
    var fragment = 20;
    var end = start + fragment;
    var left = totalResultsToRender - end ;
  
  
 // console.log( left + ' results of '+  totalResultsToRender +' total left to render');

   // partially render list
   // the thing to render, the start record and the end record
       renderPartialQuestionList(results, end-fragment, end)
       clearButton.text(end +' of '+results.length+' for '+term);
    
	//clearButton.addClass('blink');
	
    if (end >= total) {
		
        // If we reached the end, stop and change status
		clearButton.removeClass('blink');
       clearButton.text(results.length+' for '+term);
		$('body').removeClass('custom');
		//BodyRef.style.cursor = '';
		
    } else {
        // Otherwise, process next fragment
        setTimeout(function() {
            doHeavyWork(results, end, totalResultsToRender, term);
        }, 0);
    }            
}

function dowork(results, totalResultsToRender, term) {
    // Set "working" status
	
    document.getElementById("clearButton").innerHTML = "working";
	// render the single view and set term in search bar
    $('body').addClass('custom');   //document.body.style.cursor = "progress";
	renderQuestionView(results[0]);
	
    // render big view in chunks
    doHeavyWork(results, 0, totalResultsToRender, term);
}
  
  
  function searchTerm(term){
	  $('input').val(term);
    var results = null;
        results = window.idx.search(term, json_config).map(function (result) {
            return questions.filter(function (q) { return q.id === parseInt(result.ref, 10) })[0]
        })
		if(results.length<1) { renderWordList(shortlist);  }		
		else
		{
			 $("#question-list-container").empty();
		dowork(results, results.length, term);
		}	
  }
  
  window.searchTerm = searchTerm;   // Make it available via the javascript window object rather than require.js
  
  // on key up search on 3 letters or more.
  $('input').bind('keyup', debounce(function () {
    if ($(this).val().length < 2) return;

	searchTerm($(this).val());
  }))

  $("#question-list-container").delegate('li', 'click', function () {
    var li = $(this)
    var id = li.data('question-id')

    renderQuestionView(questions.filter(function (question) {
      return (question.id == id)
    })[0])
  })

})

function murmurhash3_32_gc(key, seed) {
	var remainder, bytes, h1, h1b, c1, c1b, c2, c2b, k1, i;
	
	remainder = key.length & 3; // key.length % 4
	bytes = key.length - remainder;
	h1 = seed;
	c1 = 0xcc9e2d51;
	c2 = 0x1b873593;
	i = 0;
	
	while (i < bytes) {
	  	k1 = 
	  	  ((key.charCodeAt(i) & 0xff)) |
	  	  ((key.charCodeAt(++i) & 0xff) << 8) |
	  	  ((key.charCodeAt(++i) & 0xff) << 16) |
	  	  ((key.charCodeAt(++i) & 0xff) << 24);
		++i;
		
		k1 = ((((k1 & 0xffff) * c1) + ((((k1 >>> 16) * c1) & 0xffff) << 16))) & 0xffffffff;
		k1 = (k1 << 15) | (k1 >>> 17);
		k1 = ((((k1 & 0xffff) * c2) + ((((k1 >>> 16) * c2) & 0xffff) << 16))) & 0xffffffff;

		h1 ^= k1;
        h1 = (h1 << 13) | (h1 >>> 19);
		h1b = ((((h1 & 0xffff) * 5) + ((((h1 >>> 16) * 5) & 0xffff) << 16))) & 0xffffffff;
		h1 = (((h1b & 0xffff) + 0x6b64) + ((((h1b >>> 16) + 0xe654) & 0xffff) << 16));
	}
	
	k1 = 0;
	
	switch (remainder) {
		case 3: k1 ^= (key.charCodeAt(i + 2) & 0xff) << 16;
		case 2: k1 ^= (key.charCodeAt(i + 1) & 0xff) << 8;
		case 1: k1 ^= (key.charCodeAt(i) & 0xff);
		
		k1 = (((k1 & 0xffff) * c1) + ((((k1 >>> 16) * c1) & 0xffff) << 16)) & 0xffffffff;
		k1 = (k1 << 15) | (k1 >>> 17);
		k1 = (((k1 & 0xffff) * c2) + ((((k1 >>> 16) * c2) & 0xffff) << 16)) & 0xffffffff;
		h1 ^= k1;
	}
	
	h1 ^= key.length;

	h1 ^= h1 >>> 16;
	h1 = (((h1 & 0xffff) * 0x85ebca6b) + ((((h1 >>> 16) * 0x85ebca6b) & 0xffff) << 16)) & 0xffffffff;
	h1 ^= h1 >>> 13;
	h1 = ((((h1 & 0xffff) * 0xc2b2ae35) + ((((h1 >>> 16) * 0xc2b2ae35) & 0xffff) << 16))) & 0xffffffff;
	h1 ^= h1 >>> 16;

	return h1 >>> 0;
}


