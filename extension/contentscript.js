var lastLocation = document.location.href;
var lastSelection = null;

var timer = setTimeout(function() { }, 1000);

document.addEventListener('mouseup', scheduleTracker);
document.addEventListener('keyup', scheduleTracker);

function scheduleTracker() {
    clearTimeout(timer);
    timer = setTimeout(runTracker, 5000);
}

function getBrowserUrl() {
    var url = window.location != window.parent.location
            ? document.referrer
            : document.location.href;
    return url.split('##')[0];
}

function runTracker() {
    var location = getBrowserUrl();
    var selection = window.getSelection().toString() || '';
    if (location != lastLocation || selection != lastSelection) {
        track(location, selection);
        lastLocation = location;
        lastSelection = selection;
    }
}

function getFirstBigImage() {
    function isTarget() {
        var tagName = $(this).prop('tagName');
        var bg = $(this).css('background-image');
        return (tagName === 'IMG' || tagName == 'DIV' && bg && bg != 'none') &&
            $(this).isInViewport() && $(this).width() <= 256 && $(this).height() <= 256;
    }
    var images = $('img, div')
        .filter(isTarget)
        .sort(function(a, b) {
            return $(b).width()*$(b).height() - $(a).width()*$(a).height();
        });
    if (images) {
        var img = images.eq(0);
        var src = img.attr('src') || img.css('background-image').replace('url("', '').replace('")', '');
        if (src && src.startsWith('//')) {
            src = document.location.protocol + src;
        }
        else if (src && !src.startsWith('http://') && !src.startsWith('https://') && !src.startsWith('data:')) {
            src = document.location.protocol + '//' + document.location.host + '/' + src;
        }
        return src
    }
}

function highlightSearch() {
    var parts = document.location.href.split('##');
    if (parts.length > 1) {
        window.find(parts[parts.length - 1]);
    }
}

function getFavIcon() {
    if ($("#favicon")) {
        return $("#favicon").attr("href");
    }
    return '';
}

function findKeywords() {
    try {
        return document.head.querySelector("[name=keywords]").content;
    } catch(e) {
        return [];
    }
}

function track(location, selection) {
    data = {
        type: 'track',
        url: location,
        selection: selection,
        title: document.title,
        image: getFirstBigImage(),
        favicon: getFavIcon(),
        keywords: findKeywords()
    }
    console.log('PM: track ' + JSON.stringify(data));
    chrome.runtime.sendMessage(data);
}

if (window.self == window.top) {
    scheduleTracker();
    highlightSearch();
}

console.log('Ikke: contentscript.js loaded.')
