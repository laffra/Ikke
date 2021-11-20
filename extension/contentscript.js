var myEmail = "";
var lastDataSent = "";
var essence;
var dot;
var essenceUrl;
var related = {
    query: "",
    items: []
};
var menuOpen = false;
var body = $("body");

var DEBUG = false;
var SHOW_DOT = false;

const MULTIPLIER_TOP_SCORE = 2.0;
const MULTIPLIER_CENTER_SCORE = 2.0;
const MULTIPLIER_WIDTH_SCORE = 3.0;
const MULTIPLIER_FONT_SCORE = 2.0;

const MINIMUM_OPACITY_VISIBLE = 0.5
const MINIMUM_NODE_WIDTH_VISIBLE = 10;
const MINIMUM_NODE_HEIGHT_VISIBLE = 9;

const MINIMUM_IMAGE_WIDTH = 100;
const NOMINAL_PAGE_HEIGHT = 1000.0
const DOCUMENT_CENTER = 0.4;

const PAGE_SAVER_TIMEOUT_MS = 1000;

const IKKE_URL = "http://localhost:1964/";

const DOT_SIZE = 22;
const DOT_BORDER_RADIUS = 13;
const DOT_SHADOW = "rgb(181 181 181) 0px 0px 9px 0px";
const DOT_COLOR = "#333";
const DOT_FONT_NAME = "Arial";
const DOT_FONT_SIZE = 10;

const MENU_WIDTH = 240;
const MENU_LEFT_PADDING = 5;
const MENU_TOP_PADDING = 3;
const MENU_PADDING = "3px 5px";
const MENU_BORDER_RADIUS = 7;
const MENU_COLOR = "rgb(218 221 225 / 95%)";
const MENU_FONT_NAME = "Arial";
const MENU_FONT_SIZE = 10;
const MENU_FONT_COLOR = "black";
const MENU_ICON_SIZE = 12;
const MENU_ITEM_HEIGHT = 14;
const MENU_ICON_PADDING = 5;
const MENU_ITEM_PADDING = "1px 5px"

const MENU_ITEM_BACKGROUND_COLOR = "transparent";
const MENU_ITEM_COLOR = "black";
const MENU_ITEM_BACKGROUND_COLOR_HOVER = "rgb(10, 132, 255)";
const MENU_ITEM_COLOR_HOVER = "white";

const MENU_HEADER_EXTRA_LINK_COUNT = 1;
const MENU_HEADER_ITEM_COUNT = 3;

const ANIMATION_SPEED_BACKGROUND = 200;
const ANIMATION_SPEED_MENU_OPEN = 100;
const ANIMATION_SPEED_MENU_CLOSE = 100;

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
    const nodeLeft = node.offset().left;
    if (nodeLeft > documentCenter) return 0;
    const nodeCenter = nodeLeft + node.width() / 2;
    const distance = Math.max(1, Math.abs(documentCenter - nodeCenter));
    return MULTIPLIER_CENTER_SCORE * (1.0 - distance / documentCenter);
}

function getWidthScore(node) {
    return MULTIPLIER_WIDTH_SCORE * node.width() / body.width();
}

function getFontScore(node) {
    if (node.text().length < 5) return 0;
    const fontSize = parseFloat(
        node.css("font-size").replace(/[^0-9\.]/g, "")
    );
    return MULTIPLIER_FONT_SCORE * (Math.min(40, fontSize) / 40);
}

function isVisible() {
    const node = $(this);
    if (node.height() < 5 || node.width() < 5) { console.log("too small"); return false; }
    if (node.css("visibility") == "hidden") { console.log("visibility=hidden"); return false; }
    if (node.css("display") == "none") { console.log("display=none"); return false; }
    return true;
}

function getEssenceText(node) {
    const text = node.contents().text().trim();
    const firstFiveWords = text.split(" ").slice(0, 5);
    return firstFiveWords.join(" ");
}

function findCurrentEssence() {
    var maxScore = 0;
    var newEssence;
    if (DEBUG) {
        console.log("Scan", $("span,h1,h2,h3,h4,a").filter(isContent).length, "candidates");
    }
    $("span,h1,h2,h3,h4,a").filter(isContent).each(function() {
        const node = $(this);
        const score = Math.round(100 * (
            getTopScore(node) +
            getCenterScore(node) +
            getWidthScore(node) +
            getFontScore(node)));
        if (score > maxScore) {
            newEssence = node;
            maxScore = score;
        }
        if (DEBUG) {
            showScores(node, score);
        }
    });
    return newEssence;
}

function getEssence() {
    try {
        essence = findCurrentEssence();
        const selection = getSelectedText();
        if (selection) {
            return selection;
        }
        if (essence) {
            essenceUrl = essence.closest("a").attr("href") || "";
            if (!essenceUrl.match(/https?:\/\//)) {
                if (essenceUrl.startsWith("/")) {
                    essenceUrl = document.location.protocol + "//" + document.location.hostname + essenceUrl;
                } else {
                    essenceUrl = document.location.href + "/" + essenceUrl;
                }
                console.log(essenceUrl)
            }
            return getEssenceText(essence);
        }
        return "";
    } catch (error) {
        console.log("Ikke: " + error)
        return "";
    }
}

function showScores(node, score) {
    $("<div>")
        .css({
            position: "absolute",
            top: node.offset().top,
            left: node.offset().left,
            width: node.width(),
            height: node.height() + 12,
            backgroundColor: "transparent",
            color: "black",
            border: "1px solid red"
        })
        .hover(
            function() {
                $(this)
                    .css({
                        backgroundColor: "white",
                    })
                    .text(score + " " +
                        getTopScore(node).toFixed(1) + " " +
                        getCenterScore(node).toFixed(1) + " " +
                        getWidthScore(node).toFixed(1) + " " +
                        getFontScore(node).toFixed(1)
                    );
            },
            function() {
                $(this)
                    .css({
                        backgroundColor: "transparent",
                    })
                    .text("");
            },
        )
        .appendTo(body)
}

function get_icon(item) {
    if (item.icon.startsWith("http")) {
        return item.icon;
    }
    if (item.icon.startsWith("get")) {
        return IKKE_URL + item.icon;
    }
    if (item.icon == "undefined") {
        return IKKE_URL + "get?path=icons/blue-circle.png"
    }
    return IKKE_URL + "get?path=icons/browser-web-icon.png";
}

function createTitleItem(text) {
    return $("<ikke-related-title>")
        .css({
            display: "block",
            top: 0,
            padding: MENU_ITEM_PADDING,
            width: MENU_WIDTH - 2 * MENU_LEFT_PADDING,
            height: MENU_ITEM_HEIGHT,
            lineHeight: MENU_ITEM_HEIGHT + "px",
            margin: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            border: "1px solid black",
            borderWidth: 0,
            borderBottomWidth: 1,
        })
        .text(text);
}

function createMenuItem(index) {
    return $("<ikke-related-item>")
        .css({
            display: "block",
            position: "absolute",
            top: 3 * MENU_TOP_PADDING + (MENU_ITEM_HEIGHT + 2) * index,
            backgroundColor: MENU_ITEM_BACKGROUND_COLOR,
            color: MENU_ITEM_COLOR,
            margin: 0,
            padding: MENU_ITEM_PADDING,
            width: MENU_WIDTH - 2 * MENU_LEFT_PADDING,
            height: MENU_ITEM_HEIGHT,
            overflow: "hidden",
        })
        .hover(
            function() {
                $(this).css({
                    backgroundColor: MENU_ITEM_BACKGROUND_COLOR_HOVER,
                    color: MENU_ITEM_COLOR_HOVER,
                })
            },
            function() {
                $(this).css({
                    backgroundColor: MENU_ITEM_BACKGROUND_COLOR,
                    color: MENU_ITEM_COLOR,
                })
            }
        );
}

function createMenuItemLabel(text) {
    return $("<ikke-related-name>")
        .css({
            display: "inline",
            position: "absolute",
            top: 0,
            left: MENU_ICON_SIZE + 3 * MENU_ICON_PADDING,
            backgroundColor: "transparent",
            width: MENU_WIDTH - MENU_ICON_SIZE - 3 * MENU_ICON_PADDING,
            height: MENU_ICON_SIZE,
            lineHeight: MENU_ICON_SIZE + "px",
            overflow: "hidden",
            whiteSpace: "nowrap",
            textOverflow: "ellipsis",
            fontSize: MENU_FONT_SIZE,
            fontFamily: MENU_FONT_NAME,
        })
        .text(text);
}

function getUrlAttributes(item) {
    result = "";
    Object.keys(item).forEach(function(key) {
        result += "&" + encodeURIComponent(key) + "=" + encodeURIComponent(item[key]);
    });
    return result;
}

function openMenu() {
    menuOpen = true;
    const ikkeLink = createMenuItem(1)
        .append(createMenuItemLabel('Show Ikke Graph...'))
        .click(function() {
            window.open(IKKE_URL + "?q=" + related.query);
            closeMenu();
        });
    const googleLink = createMenuItem(2)
        .append(createMenuItemLabel('Search with Google...'))
        .click(function() {
            window.open("https://google.com/search?q=" + related.query);
            closeMenu();
        });
    $("ikke-background").remove();
    const background = $("<ikke-background>")
        .appendTo(body)
        .css({
            zIndex: 1999999997,
            display: "block",
            top: 0,
            position: "fixed",
            width: body.width(),
            height: body.height(),
            backgroundColor: "transparent",
        })
        .css({
            backgroundColor: "rgb(225, 225, 225, 0.4)",
        }, ANIMATION_SPEED_BACKGROUND)
        .click(closeMenu)
        .on("keydown", function(event) {
            if (event.key == "Escape") {
                showDot();
            }
        });
    height = 3 * MENU_TOP_PADDING + (MENU_ITEM_HEIGHT + 2) * (related.items.length + MENU_HEADER_ITEM_COUNT);
    dot
        .appendTo(body)
        .empty()
        .append(createTitleItem("Ikke results for '" + related.query + "'"))
        .css({
            zIndex: 1999999998,
            textAlign: "left",
            backgroundColor: MENU_COLOR,
            padding: MENU_PADDING,
            borderRadius: MENU_BORDER_RADIUS,
        })
        .css({
            width: MENU_WIDTH,
            height: height,
        }, ANIMATION_SPEED_MENU_OPEN)
        .append(ikkeLink)
        .append(googleLink);
    const itemsContainer = $("<ikke-related-items>")
        .css({
            display: "block",
            fontSize: 0,
            margin: 0,
            padding: 0,
        })
        .appendTo(dot);
    related.items.forEach((item, index) => {
        createMenuItem(index + MENU_HEADER_ITEM_COUNT)
            .appendTo(itemsContainer)
            .click(function() {
                window.open("http://localhost:1964/render?query=" + related.query + getUrlAttributes(item));
            })
            .append(
                $("<img>")
                    .attr("src", get_icon(item))
                    .css({
                        position: "absolute",
                        top: 0,
                        width: MENU_ICON_SIZE,
                        height: MENU_ICON_SIZE,
                    }),
                createMenuItemLabel(item.label || item.title)
            );
    });
}

function closeMenu() {
    $("ikke-background").css({
        backgroundColor: "transparent",
    })
    dot.css({
        width: DOT_SIZE,
        height: DOT_SIZE,
    });
    menuOpen = false;
    showDot();
}

function showDot() {
    if (menuOpen || !SHOW_DOT || !essence || !essence.offset() || !related.items || !related.items.length) {
        return;
    }
    PAGE_SAVER_IGNORE = true;
    if (!dot) {
        dot = $("<ikke-dot>")
            .attr("id", "ikke-dot")
            .click(openMenu)
            .css({
                display: "block",
                position: "absolute",
                border: "1px solid grey",
                zIndex: 1999999998,
                overflow: "hidden",
                width: DOT_SIZE,
                height: DOT_SIZE,
                lineHeight: DOT_SIZE + "px",
                cursor: "pointer",
                boxShadow: DOT_SHADOW,
                color: DOT_COLOR,
                fontFamily: DOT_FONT_NAME,
                fontSize: DOT_FONT_SIZE,
                fontWeight: "normal",
                userSelect: "none",
                left: -100,
                right: -100,
            });
    }
    $("ikke-background").remove();
    dot
        .css( {
            textAlign: "center",
            backgroundColor: "#fff2dd",
            padding: 0,
            width: 22,
            height: 22,
            borderRadius: 13,
        })
        .css({
            opacity: 1,
        })
        .appendTo(body)
        .text((related.items.length));
    moveDotToPosition(
        essence.offset().left + essence.width() - 5,
        essence.offset().top + essence.height() / 2 - 12
    );
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

function moveDotToPosition(left, top) {
    dot.css({ left, top });
}

function savePageDetails(force) {
    if (!location.href) return;
    if (PAGE_SAVER_IGNORE) {
        PAGE_SAVER_IGNORE = false;
        return;
    }
    const data = {
        type: 'get-related-items',
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
    chrome.runtime.sendMessage(data, function(response) {
        related = response;
        showDot();
    });
}

function isContent() {
    const node = $(this);
    if (!node.isVisible()) {
        if (DEBUG && node.text().indexOf("Meyers") != -1) console.log("Not visible:", node);
        return false;
    }
    if (!node.isInViewport()) {
        if (DEBUG && node.text().indexOf("Meyers") != -1) console.log("Not in viewport:", node);
        return false;
    }
    if (node.closest("button").isVisible()) {
        if (DEBUG && node.text().indexOf("Meyers") != -1) console.log("Inside a not visible button:", node);
        return false;
    }
    if (node.attr("role") == "button") {
        if (DEBUG && node.text().indexOf("Meyers") != -1) console.log("Button:", node);
        return false;
    }
    if (node.closest("*[role='button']").position()) {
        if (DEBUG && node.text().indexOf("Meyers") != -1) console.log("Button parent:", node);
        return false;
    }
    if (node.closest("header").isVisible()) {
        return true;
    }
    if (node.attr("role") == "heading") {
        if (DEBUG && node.text().indexOf("Meyers") != -1) console.log("Heading OK:", node);
        return true;
    }
    if (node.prop("tagName") == "SPAN" && !node.css('font-weight').match(/bold|[56789][0-9][0-9]/)) {
        if (DEBUG && node.text().indexOf("Meyers") != -1) console.log("Normal span:", node);
        return false;
    }
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
    if ($(window).scrollTop()) elementTop -= 50; // focus less on header
    var elementBottom = elementTop + node.outerHeight();
    var viewportTop = $(window).scrollTop();
    var viewportBottom = viewportTop + $(window).height();
    return elementTop > viewportTop && elementBottom < viewportBottom;
};

if (window.self == window.top && !window.location.hostname.match("localhost")) {
    var pageSaver = setTimeout(savePageDetails, PAGE_SAVER_TIMEOUT_MS)
    var userInteractedWithPage = false;
    function schedulePageSaver(force) {
        clearTimeout(pageSaver);
        if (!force && !userInteractedWithPage) {
            return;
        }
        userInteractedWithPage = false
        pageSaver = setTimeout(savePageDetails, PAGE_SAVER_TIMEOUT_MS);
    }
    document.addEventListener('mousemove', () => { userInteractedWithPage = true; });
    document.addEventListener('mouseup', () => schedulePageSaver(true));
    document.addEventListener('keyup', () => schedulePageSaver(true));
    window.addEventListener('scroll', () => schedulePageSaver(true));
    body.on("DOMSubtreeModified", schedulePageSaver);
    chrome.extension.onMessage.addListener(function(request, sender, sendResponse) {
        switch (request.type) {
            case 'tab-changed':
                savePageDetails(true);
                sendResponse(request.type + " handled.");
                break;
            case 'show-ikke-dot':
                SHOW_DOT = request.value == "true";
                showDot();
                sendResponse(request.type + " handled.");
                break;
        }
    });
}