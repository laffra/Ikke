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
        sendResponse({email: email})
    }
});

function call(url, handler) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", url, true);
    if (handler) {
        xhr.addEventListener("load", function() {
            handler(this.responseText);
        });
    }
    xhr.send()
}

function send(url, data, handler) {
    var xhr = new XMLHttpRequest();
    xhr.open("POST", url, true);
    if (handler) {
        xhr.addEventListener("load", function() {
            handler(this.responseText);
        });
    }
    xhr.send(data)
}

chrome.runtime.onMessage.addListener(
    function(request, sender, sendResponse) {
        switch (request.type) {
            case 'save_page_details':
                call('http://localhost:1964/save_page_details' +
                    '?url=' + encodeURIComponent(request.url) +
                    '&title=' + encodeURIComponent(request.title) +
                    '&essence=' + encodeURIComponent(request.essence) +
                    '&email=' + encodeURIComponent(email) +
                    '&image=' + encodeURIComponent(request.image) +
                    '&selection=' + encodeURIComponent(request.selection) +
                    '&favicon=' + encodeURIComponent(request.favicon) +
                    '&keywords=' + encodeURIComponent(request.keywords || ''));
                break;
            case 'get_dot_position':
                call('http://localhost:1964/settings_get?key=dot_position_' +
                        encodeURIComponent(request.domain), function(position) {
                    sendResponse(position ? JSON.parse(position) : { right: 5, top: 5 });
                });
                break;
            case 'set_dot_position':
                call('http://localhost:1964/settings_set?key=dot_position_' +
                        encodeURIComponent(request.domain) +
                        '&value=' + JSON.stringify(request), function(position) {
                    sendMessage({
                        type: "update_dot_position",
                        domain: request.domain,
                        right: request.right,
                        top: request.top
                    });
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
    });
}

setInterval(function() {
    for (key in settings) {
        syncSetting(key);
    }
}, 1000);

function sendMessage(data) {
    chrome.tabs.query({}, function(tabs) {
        for (tab of tabs) {
            chrome.tabs.sendMessage(tab.id, data);
        } 
    });
}

function notifyTabs(activeInfo) {
    setTimeout(function() {
        for (key in settings) {
            sendMessage({ type: key, value: settings[key] });
        }
        sendMessage({ type: "tab_changed" });
    }, 100);
}

chrome.tabs.onUpdated.addListener(notifyTabs);
chrome.tabs.onActivated.addListener(notifyTabs);