if (document.location.href.startsWith('http://localhost:8081/')) {
    $('#ikke-extension').css('display', 'none');
    $('#ikke-gmail-needed').css('display', 'block');
}

console.log('Ikke: setup.js loaded.')
