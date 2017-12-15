$('#ikke-gmail-needed').css('display', 'none');

function setup_gmail() {
    document.location = 'https://myaccount.google.com/apppasswords';
}

function check_history() {
    $('.history').each(function() {
        var span = $(this);
        var kind = span.closest('tr').attr('kind');
        var load_button = $('#load-button-' + kind);
        var clear_button = $('#clear-button-' + kind);
        var spinner = $('#spinner-' + kind);
        $.getJSON('/history?kind=' + kind, function(response) {
            span.text(response.history);
            if (response.is_loading) {
                load_button.addClass('loading');
                load_button.text('Stop loading');
                spinner.css('visibility', 'visible');
            } else {
                load_button.removeClass('loading');
                load_button.text('Load more items');
                spinner.css('visibility', 'hidden');
                clear_button.attr('disabled', false);
            }
        })
        .fail(function() {
            span.text('No history for ' + kind);
            spinner.css('visibility', 'hidden');
            clear_button.remove();
        })
    })
}

setInterval(check_history, 3000);
check_history();

$('.clear-button').click(function() {
    var clear_button = $(this);
    var kind = clear_button.closest('tr').attr('kind');
    var spinner = $('#spinner-' + kind);
    var history = $('#history-' + kind);
    spinner.css('visibility', 'visible');
    clear_button.attr('disabled', true);
    $.get('/clear?kind=' + kind, function() {
        })
        .fail(function(error) {
            history.text('Error clearing ' + kind);
        })
        .done(function(error) {
            spinner.css('visibility', 'hidden');
        });
});

$('.load-button').click(function() {
    var button = $(this);
    var kind = button.closest('tr').attr('kind');
    $('#spinner-' + kind).css('visibility', 'visible');
    if (button.text() === 'Load more items') {
        $.get('/load?kind=' + kind)
            .fail(function(error) {
                $('#history-' + kind).text('Could not load more items ' + kind);
            });
    } else {
        $.get('/stopload?kind=' + kind)
            .fail(function(error) {
                $('#history-' + kind).text('Could not stop loading ' + kind);
            });
    }
    check_history();
});

function setup_extension() {
  console.log('set up extension');
  chrome.webstore.install(
    'https://chrome.google.com/webstore/detail/fmeadohikadcafhjaijonglpjdnncnal',
    function ok() {
      document.location.reload();
    },
    function fail(detail) {
      alert('Installation from Chrome webstore failed. Please use the local install option.');
      $('#ikke-extension').attr('disabled', true);
      $('#ikke-extension_local').attr('disabled', false);
    }
  );
}

function setup_extension_local() {
  document.location = '/extensions';
}

setTimeout(function() {
  $('#ikke-extension').css('opacity', 0);
});


