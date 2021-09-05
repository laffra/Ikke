var myEmail = "";
var lastDataSent = "";
var essence;
var essenceUrl;

var DEBUG = false;
var SHOW_DOT = false;

const MULTIPLIER_TOP_SCORE = 2.0;
const MULTIPLIER_FONT_SCORE = 2.0;
const MULTIPLIER_CENTER_SCORE = 1.0;

const MINIMUM_OPACITY_VISIBLE = 0.5
const MINIMUM_NODE_WIDTH_VISIBLE = 10;
const MINIMUM_NODE_HEIGHT_VISIBLE = 9;

const MINIMUM_IMAGE_WIDTH = 100;
const NOMINAL_PAGE_HEIGHT = 1000.0
const DOCUMENT_CENTER = 0.4;

const PAGE_SAVER_TIMEOUT_MS = 100;

var PAGE_SAVER_IGNORE = false;

chrome.extension.sendMessage({ kind: "ikke-email" }, function(response) {
  myEmail = response.email;
  $("#ikke-search-email").text(myEmail);
});

function getBrowserUrl() {
    var url = window.location != window.parent.location
            ? document.referrer
            : document.location.href;
    return url.split('##')[0];
}

function getSelectedText() {
    return window.getSelection().toString() || $(".kix-selection-overlay").parent().text();
}

function getFirstBigImage() {
    var images = $('img')
        .filter(function() {
            return $(this).offset() && $(this).width() > MINIMUM_IMAGE_WIDTH && $(this).isInViewport();
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

function getFavIcon() {
    return $('link[rel="shortcut icon"]').prop('href');
}

function getKeywords() {
    try {
        return document.head.querySelector("[name=keywords]").content;
    } catch(e) {
        return [];
    }
}

function hashCode(element) {
    const rect = element.getBoundingClientRect();
    return rect.left * 10000 + rect.top;
}

function getEssenceUrl() {
    return essenceUrl;
}

function getTopScore(node) {
    if (!node.position()) return 0;
    if (node.find("div").length) return 0;
    const top = node.offset().top - $(window).scrollTop();
    return MULTIPLIER_TOP_SCORE * (NOMINAL_PAGE_HEIGHT - top) / NOMINAL_PAGE_HEIGHT;
}

function getCenterScore(node) {
    const documentCenter = $(window).width() * DOCUMENT_CENTER;
    const nodeCenter = node.offset().left;
    const distance = Math.max(1, Math.abs(documentCenter - nodeCenter));
    return MULTIPLIER_CENTER_SCORE * (1.0 - distance / documentCenter);
}

function getFontScore(node) {
    if (node.text().length < 5) return 0;
    return MULTIPLIER_FONT_SCORE * Math.log(parseInt(node
        .css("font-size")
        .replace(/[^0-9]/g, "")
    ));
}

function getEssence() {
    try {
        const selection = getSelectedText();
        if (selection) return selection;
        var maxScore = 0;
        essence = undefined;
        $("span,h1,h2,h3,h4").filter(isContent).each(function() {
            const node = $(this);
            const score = Math.round(100 * (getTopScore(node) + getCenterScore(node) + getFontScore(node)));
            if (score > maxScore) {
                essence = node;
                maxScore = score;
            }
        });
        if (essence) {
            highlightEssence();
            essenceUrl = essence.closest("a").attr("href");
            return essence.text();
        }
        return "";
    } catch (error) {
        console.log("Ikke: " + error)
        return "";
    }
}

function highlightEssence() {
    $("#ikke-highlight").remove();
    if (!DEBUG || !essence) return;
    PAGE_SAVER_IGNORE = true;
    $("<div>")
        .attr("id", "ikke-highlight")
        .appendTo($("body"))
        .css("background-color", "transparent")
        .css("border", "2px solid orange")
        .css("z-index", 1000000)
        .css("position", "absolute")
        .css("width", essence.width())
        .css("height", essence.height())
        .css("left", essence.offset().left)
        .css("top", essence.offset().top)
    console.log("Ikke: essence is '" + essence.text() + "'");
}

function getTitle() {
    return $('span[role="heading"]').text() // calendar.google.com selected event summary
        || document.title;
}

function getEmails() {
    try {
        emails = [];
        $('div[data-email]').each(function() {
            const email = $(this).attr("data-email");
            if (email == myEmail) return;
            emails.push(email);
        })
        return emails.join(" ")
    } catch (error) {
        return [];
    }
}

function showDot() {
    $("#ikke-dot").remove();
    if (!SHOW_DOT) return;
    $("<div>")
    $("<ikke_dot>")
        .attr("id", "ikke-dot")
        .appendTo($("body"))
        .draggable({
            containment: "parent",
            scroll: false,
            start: function() {
                $(this).attr("dragging", "true");
            },
            drag: function() {
                chrome.runtime.sendMessage({
                    type: "set_dot_position",
                    domain: document.location.hostname,
                    right: $(window).width() - $(this).offset().left - $(this).width(), 
                    top: $(this).offset().top,
                })
            },
            stop: function() {
                $(this).attr("dragging", "false");
            },
          })
        .css("background-color", "#fff2dd")
        .css("border", "1px solid grey")
        .css("z-index", 1999999998)
        .css("display", "block")
        .css("position", "fixed")
        .css("width", 22)
        .css("height", 22)
        .css("border-radius", 13)
        .css("right", -25)
        .css("top", 5)
        .css("cursor", "pointer")
        .css("box-shadow", "rgb(181 181 181) 0px 0px 9px 0px")
        .append($("<ikke_dot_label>")
            .css("position", "absolute")
            .css("display", "block")
            .css("background-color", "transparent")
            .css("color", "#333")
            .css("font-family", "Arial")
            .css("font-size", 12)
            .css("font-weight", "normal")
            .css("user-select", "none")
            .css("top", 4)
            .css("left", 4)
            .text("10")
        );
    positionDot();
    console.log("Ikke: show dot");
}

function moveDotToPosition(right, top) {
    if ($("#ikke-dot").attr("dragging") == "true") return;
    console.log("moveDotToPosition", right, top);
    $("#ikke-dot")
        .css("right", Math.min($(window).width(), right))
        .css("top", Math.min($(window).height(), top));
}

function positionDot() {
    chrome.runtime.sendMessage({
        type: "get_dot_position",
        domain: document.location.hostname,
    }, function(response) {
        moveDotToPosition(response.right, response.top);
    });
}

function savePageDetails(force) {
    if (!location.href) return;
    if (PAGE_SAVER_IGNORE) {
        PAGE_SAVER_IGNORE = false;
        return;
    }
    const data = {
        type: 'save_page_details',
        selection: getSelectedText(),
        title: getTitle(),
        image: getFirstBigImage(),
        emails: getEmails(),
        favicon: getFavIcon(),
        essence: getEssence(),
        url: getEssenceUrl() || location.href,
        keywords: getKeywords(),
    };
    const dataString = JSON.stringify(data);
    if (force == undefined && dataString == lastDataSent) return;
    lastDataSent = dataString;
    chrome.runtime.sendMessage(data);
}

function isContent() {
    const node = $(this);
    if (!node.isVisible()) return false;
    if (!node.isInViewport()) return false;
    if (node.closest("button").position()) return false;
    if (node.attr("role") == "button") return false;
    if (node.closest("*[role='button']").position()) return false;
    if (node.attr("role") == "heading") return true;
    if (node.prop("tagName") == "SPAN" && !node.css('font-weight').match(/bold|[56789][0-9][0-9]/)) return false;
    return true;
}

$.fn.isVisible = function() {
    const node = $(this);
    if (node.css("display") == "none") return false;
    if (node.css("opacity") < MINIMUM_OPACITY_VISIBLE) return false;
    if (node.width() < MINIMUM_NODE_WIDTH_VISIBLE) return false;
    if (node.height() < MINIMUM_NODE_HEIGHT_VISIBLE) return false;
    return true;
};

$.fn.isInViewport = function() {
    const node = $(this);
    var elementTop = node.offset().top;
    if ($(window).scrollTop()) elementTop -= 100; // focus less on header
    var elementBottom = elementTop + node.outerHeight();
    var viewportTop = $(window).scrollTop();
    var viewportBottom = viewportTop + $(window).height();
    return elementTop > viewportTop && elementBottom < viewportBottom;
};

if (window.self == window.top && !window.location.hostname.match("localhost")) {
    var pageSaver = setTimeout(savePageDetails, PAGE_SAVER_TIMEOUT_MS)
    function schedulePageSaver() {
        clearTimeout(pageSaver);
        pageSaver = setTimeout(savePageDetails, PAGE_SAVER_TIMEOUT_MS);
    }
    document.addEventListener('mouseup', schedulePageSaver);
    document.addEventListener('keyup', schedulePageSaver);
    window.addEventListener('scroll', schedulePageSaver);
    $("body").on("DOMSubtreeModified", schedulePageSaver);
    chrome.extension.onMessage.addListener(function(request, sender, sendResponse) {
        switch (request.type) {
            case 'tab_changed':
                savePageDetails(true);
                break;
            case 'update_dot_position':
                console.log("update dot", request);
                if (request.domain == document.location.hostname) {
                    moveDotToPosition(parseInt(request.right), parseInt(request.top));
                }
                break;
            case 'show-ikke-dot':
                SHOW_DOT = request.value == "true";
                showDot();
                break;
            case 'debug-browser-extension':
                DEBUG = request.value == "true";
                highlightEssence();
                break;
        }
    });
}