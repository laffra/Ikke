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
                    '&image=' + encodeURIComponent(request.image) +
                    '&selection=' + encodeURIComponent(request.selection) +
                    '&favicon=' + encodeURIComponent(request.favicon) +
                    '&keywords=' + encodeURIComponent(request.keywords || ''));
                break;
        }
        return true;
    }
);
