$('#ikke-done')
    .attr('disabled', true)

$('#ikke-balloon')
    .css('top', '370px')

function data_entered() {
    return document.location.href.endsWith('/fb-login/') ||
        $('#ikke-app-id').val().length && $('#ikke-app-secret').val().length;
}

if (document.location.href.endsWith('/fb-login/')) {
    $('#ikke-steps-settings').css('display', 'none');
    $('#ikke-balloon')
        .css('width', '180px')
    $("#ikke-title").text('IKKE Instructions - Step 3/4')
    enable();
} else {
    $("#ikke-title").text('IKKE Instructions - Step 2/4')
    $('#ikke-steps-fb-login').css('display', 'none');
}

function enable() {
    $('#ikke-done')
        .attr('disabled', false)
        .css('background', data_entered() ? '#db4437' : '#EEE');
}

function watch(id) {
    $(id).on('change', enable).on('input', enable).on('keyup', enable);
}

watch('#ikke-app-id');

watch('#ikke-app-secret');

$('#ikke-done').on('click', function() {
    var id = $('#ikke-app-id').val();
    var secret = $('#ikke-app-secret').val();
    document.location = 'http://localhost:1964/setupfacebook?appid=' + id + '&appsecret=' + secret;
});
