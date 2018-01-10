$.each($('div'), function(index, div) {
    if ($(div).text().endsWith('@gmail.com')) {
        $('#ikke-username').val($(div).text());
    }
});

function enable_button() {
    $('#ikke-done').css('background', $('#ikke-password').val().length == 16 ? '#db4437' : '#EEE');
}
$('#ikke-password').on('keyup', enable_button).on('input', enable_button);
$('#ikke-done').on('click', function() {
    if ($('#ikke-password').val().length == 16 && $('#ikke-username').val()) {
        var gu = $('#ikke-username').val();
        var gp = $('#ikke-password').val();
        document.location = 'http://localhost:1964/setup?gp=' + gp + '&gu=' + gu;
    }
});
