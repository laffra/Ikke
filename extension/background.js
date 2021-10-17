var email = "???";

const settings = {
    "debug-browser-extension": "",
    "show-ikke-dot": "",
}

chrome.identity.getProfileUserInfo(function(info) {
    email = info.email;
});

chrome.extension.onMessage.addListener(function(request, sender, sendResponse) {
    if (request.kind == "ikke-email") {
        sendResponse({email: email});
    }
});

function call(url, handler) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", url, true);
    xhr.addEventListener("load", function() {
        handler(this.responseText);
    });
    xhr.send();
}

chrome.runtime.onMessage.addListener(
    function(request, sender, sendResponse) {
        if (!sender.tab.active) return;
        switch (request.type) {
            case 'get-related-items':
                call('http://localhost:1964/get_related_items' +
                    '?url=' + encodeURIComponent(request.url) +
                    '&title=' + encodeURIComponent(request.title) +
                    '&essence=' + encodeURIComponent(request.essence) +
                    '&email=' + encodeURIComponent(email) +
                    '&image=' + encodeURIComponent(request.image) +
                    '&selection=' + encodeURIComponent(request.selection) +
                    '&favicon=' + encodeURIComponent(request.favicon) +
                    '&keywords=' + encodeURIComponent(request.keywords || ''), function(response) {
                        sendResponse(JSON.parse(response));
                    });
                break;
        }
        return true;
    }
);

function syncSetting(key) {
    call('http://localhost:1964/settings_get?key=' + key, function(response) {
        if (settings[key] != response) {
            settings[key] = response;
            sendMessage({ type: key, value: settings[key] });
        }
    }, true);
}

setInterval(function() {
    for (key in settings) {
        syncSetting(key);
    }
}, 1000);

function sendMessage(data) {
    chrome.tabs.query({}, function(tabs) {
        for (tab of tabs) {
            console.log("send", tab.id, data.kind);
            chrome.tabs.sendMessage(tab.id, data, function(response) {
                console.log(tab.id, response);
            });
        } 
    });
}

function notifyTabs(activeInfo) {
    setTimeout(function() {
        for (key in settings) {
            sendMessage({ type: key, value: settings[key] });
        }
        sendMessage({ type: "tab-changed" });
    }, 100);
}

chrome.tabs.onUpdated.addListener(function(tabId) { notifyTabs({ tabId })});
chrome.tabs.onActivated.addListener(notifyTabs);

chrome.contextMenus.create({
    title: "Search Ikke for \"%s\"",
    contexts: ["selection"], 
    onclick: function(info, tab) {
        console.log("search ikke", info);
        window.open('http://localhost:1964/?q=' + info.selectionText);
    },
});