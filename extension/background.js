var email = "???";

chrome.identity.getProfileUserInfo(function(info) {
    email = info.email;
    console.log("email:", email)
});

chrome.extension.onMessage.addListener(function(request, sender, sendResponse) {
    if (request.kind == "ikke-email") {
        sendResponse({email: email})
        console.log("send response:", email)
    }
});

function call(url, handler) {
    console.log('call url ' + url)
    var xhr = new XMLHttpRequest();
    xhr.open("GET", url, true);
    if (handler) {
        xhr.addEventListener("load", function() {
            handler(this.responseText);
        });
    }
    xhr.send();
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
            case 'save_image':
                call('http://localhost:1964/save_image' +
                    '?url=' + encodeURIComponent(request.url) +
                    '&title=' + encodeURIComponent(request.title) +
                    '&email=' + encodeURIComponent(email) +
                    '&image=' + encodeURIComponent(request.image) +
                    '&selection=' + encodeURIComponent(request.selection) +
                    '&favicon=' + encodeURIComponent(request.favicon) +
                    '&keywords=' + encodeURIComponent(request.keywords || ''));
                break;
        }
        return true;
    }
);
