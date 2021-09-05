$('#ikke-gmail-needed').css('display', 'none');

function check_history() {
    $.getJSON('/status', function(response) {
        $('.history').each(function() {
            var span = $(this);
            var kind = span.closest('tr').attr('kind');
            var load_button = $('#load-button-' + kind);
            var stop_load_button = $('#stop-load-button-' + kind);
            var clear_button = $('#clear-button-' + kind);
            var stop_clear_button = $('#stop-clear-button-' + kind);
            var spinner = $('#spinner-' + kind);
            var status = response[kind]
            var running = status.loading || status.deleting;
            span.text(status.history);
            spinner.css('visibility', running ? 'visible' : 'hidden');
            load_button.css('display', status.loading ? 'none' : 'block');
            stop_load_button.css('display', status.loading ? 'block' : 'none');
            clear_button.css('display', status.count == 0 || status.deleting ? 'none' : 'block');
            stop_clear_button.css('display', status.count > 0 && status.deleting ? 'block' : 'none');
        })
        setTimeout(check_history, 1000);
    })
    .fail(function() {
        span.text('No history for ' + kind);
        spinner.css('visibility', 'hidden');
        load_button.css('visibility', 'hidden');
        clear_button.css('visibility', 'hidden');
        setTimeout(check_history, 10000);
    })
}

check_history();

$('.logo').click(function() {
    document.location = '/';
});

$('.load-button').click(function() {
    var kind = $(this).closest('tr').attr('kind');
    $.get('/load?kind=' + kind)
        .fail(function(error) {
            $('#history-' + kind).text('Could not load more items, ' + error);
        }
    );
});

$('.stop-load-button').click(function() {
    var kind = $(this).closest('tr').attr('kind');
    $.get('/stopload?kind=' + kind)
        .fail(function(error) {
            $('#history-' + kind).text('Could not stop loading, ' + error);
        }
    );
});

$('.clear-button').click(function() {
    var kind = $(this).closest('tr').attr('kind');
    $.get('/clear?kind=' + kind)
        .fail(function(error) {
            $('#history-' + kind).text('Could not clear items, ' + error);
        }
    );
});

$('.stop-clear-button').click(function() {
    var kind = $(this).closest('tr').attr('kind');
    $.get('/stopclear?kind=' + kind)
        .fail(function(error) {
            $('#history-' + kind).text('Could not stop deleting, ' + error);
        });
});

$('#settings-debug-browser-extension').on('change', function () {
    $.get('/settings_set?key=debug-browser-extension&value=' + $(this).is(":checked"))
        .done(function(result) {
            console.log(result);
        })
        .fail(function(error) {
            alert(error);
        });
});

$.get('/settings_get?key=debug-browser-extension')
    .done(function(result) {
        $('#settings-debug-browser-extension').prop('checked', result == "true");
    })
    .fail(function(error) {
        alert(error);
    });

$('#settings-show-ikke-dot').on('change', function () {
    console.log("dot?", $(this).is(":checked"));
    $.get('/settings_set?key=show-ikke-dot&value=' + $(this).is(":checked"))
        .done(function(result) {
            console.log("dot?", $(this).is(":checked"), result);
        })
        .fail(function(error) {
            alert(error);
        });
});

$.get('/settings_get?key=show-ikke-dot')
    .done(function(result) {
        $('#settings-show-ikke-dot').prop('checked', result == "true");
    })
    .fail(function(error) {
        alert(error);
    });

function setup_extension() {
    window.open("http://chrislaffra.com/ikke/extension.html", '_blank');
}

setInterval(function() {
  if ($('#ikke-extension').css('display') == 'block') {
    document.location.reload();
  }
}, 30000)

