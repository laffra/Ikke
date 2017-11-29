from collections import defaultdict
from urllib.parse import urlparse

work = defaultdict(str)


def get_key(url):
    domain = urlparse(url).netloc
    path = urlparse(url).path
    key = '%s%s' % (domain, path)
    return key


def activate(key):
    work[key] = tasks[key]


def get_work(url):
    return work[get_key(url)]


tasks = {
    'myaccount.google.com/apppasswords': '''
        <h2>IKKE Instructions</h2>
        To create a new Google app password for IKKE, please follow these instructions:
        <ol>
        <li>Verify your gmail address below:<br><input style="width:180px" id="pim-username"/>
        <li>Click "Select app" in the dialog at the right
        <li>Choose "Other <i>(custom name)</i>"
        <li>Enter "IKKE" as the name
        <li>Click <span style="background: #4285f4; padding:4px; border-radius: 3px; color: #fff;">GENERATE</span>
        <li>Copy-paste the password here:<br><input style="width:180px" id="pim-password"/>
        </ol>
        <br><br>
        <span id="pim-done"
            style="background:#eee; cursor:pointer; padding:6px; border-radius:3px; color:#fff;"
        >DONE</span>
        <script>
            console.log('IKKE: find username');
            $.each($('div'), function(index, div) {
                if ($(div).text().endsWith('@gmail.com')) {
                    $('#pim-username').val($(div).text());
                }
            });
        </script>
        <script>
            console.log('IKKE: set up handler for pim-done');
            function enable_button() {
                $('#pim-done').css('background', $('#pim-password').val().length == 16 ? '#db4437' : '#EEE');
            }
            $('#pim-password').on('keyup', enable_button).on('input', enable_button);
            $('#pim-done').on('click', function() {
                if ($('#pim-password').val().length == 16 && $('#pim-username').val()) {
                    var gu = $('#pim-username').val();
                    var gp = $('#pim-password').val();
                    document.location = 'http://localhost:8081/setup?gp=' + gp + '&gu=' + gu;
                }
            });
        </script>
    ''',
}

