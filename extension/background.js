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
            case 'track':
                call('http://localhost:8081/track' +
                    '?url=' + encodeURIComponent(request.url) +
                    '&title=' + encodeURIComponent(request.title) +
                    '&image=' + encodeURIComponent(request.image) +
                    '&selection=' + encodeURIComponent(request.selection) +
                    '&favicon=' + encodeURIComponent(request.favicon) +
                    '&keywords=' + encodeURIComponent(request.keywords || ''));
                break;
            case 'dothis':
                call('http://localhost:8081/dothis?url=' + encodeURIComponent(request.url), function(response) {
                    sendResponse(response);
                });
                break;
        }
        return true;
    }
);

console.log('Ikke: background.js loaded.')
