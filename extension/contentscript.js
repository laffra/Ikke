var lastLocation = document.location.href;
var lastSelection = null;
var email = "";

chrome.extension.sendMessage({ kind: "ikke-email" }, function(response) {
  email = response.email;
  $("#ikke-search-email").text(email);
});

var timer = setTimeout(function() { }, 1000);

document.addEventListener('mouseup', scheduleExtractor);
document.addEventListener('keyup', scheduleExtractor);

function scheduleExtractor() {
    clearTimeout(timer);
    timer = setTimeout(runExtractor, 1000);
}

function getBrowserUrl() {
    var url = window.location != window.parent.location
            ? document.referrer
            : document.location.href;
    return url.split('##')[0];
}

function getSelectedText() {
    return window.getSelection().toString() || $(".kix-selection-overlay").parent().text();
}

function runExtractor() {
    var location = getBrowserUrl();
    var selection = getSelectedText();
    if (location != lastLocation || selection != lastSelection) {
        save_image(location, selection);
        lastLocation = location;
        lastSelection = selection;
    }
}

function getFirstBigImage() {
    var images = $('img')
        .filter(function() {
            return $(this).offset() && $(this).width() > 100 && $(this).isInViewport();
        })
        .sort(function(a, b) {
            const squareA = Math.abs($(a).width() - $(a).height());
            const squareB = Math.abs($(b).width() - $(b).height());
            return squareA - squareB;
        });
    if (images.length) {
        var img = images.eq(0);
        var src = img.attr('src');
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
    return $('link[rel="shortcut icon"]').prop('href');
}

function findKeywords() {
    try {
        return document.head.querySelector("[name=keywords]").content;
    } catch(e) {
        return [];
    }
}

function save_image(location, selection) {
    data = {
        type: 'save_image',
        url: location,
        selection: selection,
        title: document.title,
        image: getFirstBigImage(),
        favicon: getFavIcon(),
        keywords: findKeywords()
    }
    chrome.runtime.sendMessage(data);
}

if (window.self == window.top) {
    scheduleExtractor();
    highlightSearch();
}
