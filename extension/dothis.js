chrome.runtime.sendMessage({ type: 'dothis', url: document.location.href}, function(response) {
    if (response) {
        $('<div>')
            .css('width', '250px')
            .css('background', 'lightyellow')
            .css('cursor', 'move')
            .css('margin', '16px')
            .css('padding', '16px')
            .css('position', 'absolute')
            .css('left', '10px')
            .css('top', ($(window).height() / 3) + 'px')
            .css('box-shadow', '0 4px 4px 0 rgba(0,0,0,0.16), 0 0 0 1px rgba(0,0,0,0.08)')
            .html(response)
            .draggable()
            .appendTo($(document.body))
    }
})

