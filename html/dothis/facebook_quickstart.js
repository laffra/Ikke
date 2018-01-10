
setInterval(function() {
    if (document.location.href.endsWith('?platform=web')) {
        var appID = document.location.pathname.split('/')[2]
        if (appID) {
            var url = 'developers.facebook.com/apps';
            var args = appID +'/settings/';
            document.location = 'http://localhost:1964/continuesetup?url=' + url + '&args=' + args;
        }
    }
}, 1000)
