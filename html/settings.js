$('#ikke-gmail-needed').css('display', 'none');

function setup_gmail() {
    document.location = 'https://myaccount.google.com/apppasswords';
}

function check_history() {
    $('.history').each(function() {
        var span = $(this);
        var kind = span.parent().attr('kind');
        if (span.text()) {
            $.get('/history?kind=' + kind, function(history) {
                span.text(history);
                var button = $('#load-button-' + kind);
                if (history.indexOf('Loading more items') != -1) {
                    button.addClass('loading');
                    button.text('Stop loading');
                    $('#spinner-' + kind).css('visibility', 'visible');
                } else {
                    button.removeClass('loading');
                    button.text('Load more items');
                    $('#spinner-' + kind).css('visibility', 'hidden');
                }
            })
            .fail(function() {
                span.text('Error getting history for ' + kind);
            })
        }
    })
}

setInterval(check_history, 3000);
check_history();

$('.clear-button').click(function() {
    var button = $(this);
    var kind = button.parent().attr('kind');
    $('#spinner-' + kind).css('visibility', 'visible');
    button.attr('disabled', true);
    $.get('/clear?kind=' + kind, function() {
            var li = button.closest('li');
            button.animate({ fontSize: 0 }, 500);
            li.animate({ height: 0 }, 500, function() { li.empty().remove() });
        })
        .fail(function(error) {
            $('#history-' + kind).text('Error clearing ' + kind);
        })
        .done(function(error) {
            $('#spinner-' + kind).css('visibility', 'hidden');
            if (kind == 'all') {
                $('.clear-button').attr('disabled', true);
            }
        });
});

$('.load-button').click(function() {
    var button = $(this);
    var kind = button.parent().attr('kind');
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


