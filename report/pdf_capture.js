var system = require('system');
var page = require("webpage").create();
var url, outfile, vp_width, vp_height;

page.onError = function(msg, trace) {
  var msgStack = ['ERROR: ' + msg];

  if (trace && trace.length) {
    msgStack.push('TRACE:');
    trace.forEach(function(t) {
      msgStack.push(' -> ' + t.file + ': ' + t.line + (t.function ? ' (in function "' + t.function +'")' : ''));
    });
  }
  console.error(msgStack.join('\n'));
};

page.onConsoleMessage = function(msg, lineNum, sourceId) {
  console.log('CONSOLE: ' + msg + ' (from line #' + lineNum + ' in "' + sourceId + '")');
};

if (system.args.length != 5) {
    console.log('Usage: pdf_capture.js URL filename window_width window_height');
    phantom.exit(1);
} else {
	url = system.args[1];
	outfile = system.args[2];
	vp_width = parseInt(system.args[3]);
	vp_height = parseInt(system.args[4]);
	page.viewportSize = { width:vp_width, height:vp_height };
	page.paperSize = { width:vp_width+'px', height:vp_height+12+'px', margin: '0px' }; // Add 12 pixels of height to keep PDF on 1 page

	function onPageReady() {
	    var htmlContent = page.evaluate(function () {
	        return document.documentElement.outerHTML;
	    });
	    //console.log(htmlContent);
		page.render(outfile);
		console.log('Wrote output file: ' + outfile);
	    phantom.exit();
	}

	console.log('\nOpening page: ' + url);
	page.open(url, function (status) {
	    function checkReadyState() {
	        setTimeout(function () {
	            var readyState = page.evaluate(function () {
					return ((typeof cybex_chart4 !== 'undefined') && (cybex_chart4.data().length > 0));
	            });

	            if (readyState) {
	                setTimeout(function () { onPageReady() }, 1000);  // Wait for d3 transition to complete after data has been rec'd
	            } else {
	                checkReadyState();
	            }
	        }, 200);
	    }
	    checkReadyState();
	});
}