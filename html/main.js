const NORMAL_ICON_SIZE = 32;

var spinner_needed = true;

var RENDER_AS_GRID = localStorage.rendertype == 'grid';

function init_tabs() {
    $('#tabs')
        .tabs({
            active : localStorage.getItem('tab', 0),
            activate : function(event, ui) {
                if (ui.newTab.attr('remember') == 'true') {
                    localStorage.tab = ui.newTab.parent().children().index(ui.newTab);
                }
            }
        })
        .css('display', 'block')
    $('#google').click(search_google);
    $('#settings').click(settings);
}

function rerender(kind) {
    remember_filters(kind);
    document.location = "/?q=" + $('#query').val();
}

function get_preference(key, otherwise) {
    if (localStorage[key] == null) {
        return otherwise;
    }
    return localStorage[key];
}

function set_preference(key, value) {
    localStorage[key] = value;
}

function show_duplicates() {
    document.location = "/?d=1&q=" + localStorage.query;
}

function settings() {
    $(document.body)
        .css('background', 'white')
        .html('<img src="get?path=icons/loading_spinner.gif" class="spinner">');
    document.location = "/settings";
}

function search_google() {
    $(document.body)
        .css('background', 'white')
        .html('<img src="get?path=icons/loading_spinner.gif" class="spinner">');
    document.location = "https://www.google.com/search?q=" + localStorage.query;
}

function init_filters() {
    if (localStorage.query && !$.hasUrlParams()) {
        document.location = "/?q=" + localStorage.query;
    }
    var query = $.urlParam('q').replace(/\+/g, ' ') || localStorage.query || '';
    $("#duration").val(get_preference('durationl') || 'month');
    $("#rendertype").val(get_preference('rendertype') || 'graph');
    $("#query").val(query);
    $('#toolbar').css('display', 'block');
    remember_filters('all')
    return query;
}

function remember_filters(kind) {
    set_preference("query", $("#query").val());
    set_preference("duration", $("#duration-" + kind).val() || get_preference('duration') || 'month')
    set_preference("rendertype", $("#rendertype-" + kind).val() || get_preference('rendertype') || 'graph')
}

function get_args(query, kind) {
    var duration = get_preference("duration") || "month";
    var duplicates = $.urlParam('d') || '0';
    return 'd=' + duplicates + '&q=' + query + '&duration=' + duration + '&kind=' + kind;
}

function render() {
    var w = window.innerWidth;
    var h = window.innerHeight;

    $(".sad")
        .css('margin-top', (h/9)+"px");
    $(".spinner")
        .css('margin-top', (h/9)+"px");

    init_tabs();
    query = init_filters();
    document.title = "Ikke " + query;
    $('.search-button').on('click', function() {
        rerender('all');
        document.location.reload();
    });
    setTimeout(function() {
        if (spinner_needed) {
            $(".spinner").css("display", "block");
        }
    }, 500);

    window.onpopstate = function(e){
        if (e.state) {
            document.getElementById("query").value = e.state;
            document.title = e.state.pageTitle;
        }
    };

    $.get("search?" + get_args(query, ''), function() {
        kinds.forEach(function(kind) {
            if (RENDER_AS_GRID) {
                load_grid(kind, w, h);
            } else {
                load_graph(kind, w, h);
            }
        });
    })
}

function nobreaks(html) {
    return html.replace(' ', '&nbsp;');
}

function load_grid(kind, w, h) {
    d3.json("graph?" + get_args(query, kind), function(error, graph) {
        clear_spinner(kind, error, graph);
        update_summary(kind, graph);
        if (graph.nodes.length) {
            var table = $('<table class="ui-table">').appendTo($('#tabs-' + kind).children().first());
            table.append($('<tr>').append([
                $('<th colspan=2>').text('Title'),
                $('<th>').text('Date'),
                $('<th>').text('Who'),
            ]));
        }
        var sorted_nodes = graph.nodes.sort(function compare(a, b) {
            return a.kind < b.kind ? 1 : -1;
        });
        $.each(sorted_nodes, function(index, node) {
            if (node.kind == kind || (kind == 'all' && node.kind != 'label')) {
                table.append($('<tr>')
                    .on("click", function() {
                        var row = $(this);
                        launch(row.attr('kind'), row.attr('label'), row.attr('url'), row.attr('path'));
                    })
                    .attr('kind', node.kind)
                    .attr('label', node.label)
                    .attr('url', node.url)
                    .attr('path', node.path)
                    .append([
                        $('<td width=20>').append(
                            $('<img>').attr('src', node.icon).css('width', '16px')
                        ),
                        $('<td>').text(node.url || node.subject || node.label),
                        $('<td>').html(nobreaks(node.date)),
                        $('<td>').html(nobreaks(node.senders && node.senders[0].label || '')),
                    ]));
            }
        })
    });
}

function clear_spinner(kind, error, graph) {
    spinner_needed = false;
    $(".spinner").css("display", "none");
    if (error) {
        $('#stats-' + kind).text('An internal error occurred. Details: ' + error);
        $("#sad-" + kind).css("display", "block");
        $("#sadmessage-" + kind).text(error);
        throw error;
    }
    if (graph.nodes.length == 0) {
        $("#sad-" + kind).css("display", "block");
        $("#sadmessage-" + kind).text("Nothing found. Please try a different search, or...");
    }
    $('#stats-' + kind).text('');
}

function update_summary(kind, graph) {
    var duration = {
        day: 'the last day',
        week: 'the last week',
        month: 'the last month',
        month3: 'the last three months',
        month6: 'the last six months',
        year: 'the last year',
        forever: 'since forever'
    }[get_preference("duration") || 'month'];

    var rendertype = get_preference("rendertype") || 'graph';

    var count = graph.nodes.filter(function(node) { return node.kind != 'label'; }).length;
    var stats = JSON.parse(graph.stats);
    var removed = stats.removed ? (
             ', with ' +
            '<a href=# class="summary-removed-' + kind + '">' + stats.removed +
            ' similar results</a> removed,'
        ) : '';
    $('#summary-' + kind).html(
        'Showing ' + count + ' results' + removed + ' for ' +
        '<div class="summary-link" id="summary-duration-' + kind + '"><a href=#>' + duration + '</a></div>' +
        ' as a ' +
        '<div class="summary-link" id="summary-rendertype-' + kind + '"><a href=#>' + rendertype + '</a></div>'
    );
    $('#summary-duration-' + kind + ' a').click(function() {
        $('#summary-duration-' + kind)
            .empty()
            .append($('<select>')
                .addClass('filter')
                .attr('id', 'duration-' + kind)
                .on('change', function() { rerender(kind); })
                .append([
                    $('<option>').attr('value', 'day').text('the last day'),
                    $('<option>').attr('value', 'week').text('the last week'),
                    $('<option>').attr('value', 'month').text('the last month'),
                    $('<option>').attr('value', 'month3').text('the last three months'),
                    $('<option>').attr('value', 'month6').text('the last six months'),
                    $('<option>').attr('value', 'year').text('the last year'),
                    $('<option>').attr('value', 'forever').text('since forever'),
                ])
            );
        $('#duration-' + kind)
            .val(get_preference('duration', 'month'))
            .parent().parent().css('margin', '6px 0 2px 4px');
    });
    $('#summary-rendertype-' + kind + ' a').click(function() {
        $('#summary-rendertype-' + kind)
            .empty()
            .append($('<select>')
                .addClass('filter')
                .attr('id', 'rendertype-' + kind)
                .on('change', function() { rerender(kind); })
                .append([
                    $('<option>').attr('value', 'graph').text('graph'),
                    $('<option>').attr('value', 'grid').text('grid'),
                ])
            );
        $('#rendertype-' + kind)
            .val(get_preference('rendertype', 'graph'))
            .parent().parent().css('margin', '6px 0 2px 4px');
    })
    $('.summary-removed-' + kind).click(show_duplicates);

    if (rendertype === "graph") {
        $(".zoom-buttons")
            .css('display', "inline-block");
    }
}

function load_graph(kind, w, h) {
    var force = d3.forceSimulation()
            .force("link", d3.forceLink().id(function(d) { return d.index }))
            .force("charge", d3.forceManyBody())
            .force("center", d3.forceCenter(w/3, h/2))
            .force("x", d3.forceX(0.1))
            .force("y", d3.forceY(0.1))
            .alpha(0.4)
            .alphaDecay(0.05);

    var w = $(window).width();
    var h = $(window).height();
    var zoom = d3.zoom().scaleExtent([0.3, 2]).on("zoom", zoomed);
    var svg = d3.select("#tabs-" + kind)
        .append("svg")
        .style("cursor", "move")
        .attr("width", w - 2 * $('.logo').width() - 96)
        .attr("height", h)
        .call(zoom);
    var g = svg.append("g");
    var current_zoom_scale = 0.8;
    zoom.scaleTo(svg, current_zoom_scale);

    function zoomed(a, b, c) {
        current_zoom_scale = d3.event.transform.k;
        g.style("stroke-width", 1.5 / d3.event.transform.k + "px");
        g.attr("transform", d3.event.transform);
    }

    d3.selectAll('#zoom-in-' + kind).on('click', function() {
        zoom.scaleTo(svg, current_zoom_scale *= 1.3);
    });

    d3.selectAll('#zoom-out-' + kind).on('click', function() {
        zoom.scaleTo(svg, current_zoom_scale *= 0.7);
    });

    d3.json("graph?" + get_args(query, kind), function(error, graph) {
        clear_spinner(kind, error, graph);

        update_summary(kind, graph);

        zoom.scaleTo(svg, current_zoom_scale = Math.min(.8, 40/graph.nodes.length));
        console.log('zoom to ' + current_zoom_scale);

        svg.insert("rect", ":first-child")
            .attr("id", "background-" + kind)
            .attr("fill", 'white')
            .attr("width", w)
            .attr("height", h)
            .on("click", function() { shake(0.5); });
        setCollideRadius();

        var linkedByIndex = {};
        graph.links.forEach(function(d) {
            linkedByIndex[d.source + "," + d.target] = true;
        });

        function isConnected(a, b) {
            return linkedByIndex[a.index + "," + b.index] || linkedByIndex[b.index + "," + a.index] || a.index == b.index;
        }

        function hasConnections(a) {
            for (var property in linkedByIndex) {
                s = property.split(",");
                if ((s[0] == a.index || s[1] == a.index) && linkedByIndex[property]) return true;
            }
            return false;
        }

        function getId(d, type) {
            var label = d.label || '';
            var url = d.url || '';
            var uid = d.uid || '';
            return (type || "t") + "_" + kind + '_' + (uid+label+url).replace(/[^a-z0-9]/gi, "");
        }

        function selectId(d, type) {
            return "#" + getId(d, type);
        }

        function zoomInNode(d) {
            var keep_duplicates = $.urlParam('d') == '1';
            if (d.kind !== 'label') {
                d3.select(selectId(d, 'border'))
                    .transition()
                    .style("stroke", "#555")
                    .style("stroke-width", "4px")
                    .attr("x", function(d) { return -d.zoomed_icon_size/2 - 2; })
                    .attr("y", function(d) { return -d.zoomed_icon_size/2 - 2; })
                    .attr("width", function(d) { return d.icon_size > 32 ? d.zoomed_icon_size + 4 : 0; })
                    .attr("height", function(d) { return d.zoomed_icon_size + 4; })
                d3.select(selectId(d, 'text'))
                    .text(function(d) {
                        return (d.title || d.label)
                            .replace(/\?.*/, '')
                            .replace(/https+:\/\/[^\/]*\//, '')
                    })
                    .transition()
                    .attr("y", function(d) { return 2 + 2 * Math.max(16, d.font_size) + d.zoomed_icon_size/2; })
                    .style("font-size", function(d) { return 2 * Math.max(16, d.font_size) + 'px'; })
                d3.select(this)
                    .transition()
                    .attr("x", function(d) { return -d.zoomed_icon_size/2; })
                    .attr("y", function(d) { return -d.zoomed_icon_size/2; })
                    .attr("width", function(d) { return d.zoomed_icon_size; })
                    .attr("height", function(d) { return d.zoomed_icon_size; })
            }
        }

        function zoomOutNode(d) {
            d3.select(this);
            if (d.kind !== 'label') {
                d3.select( this )
                    .transition()
                    .attr("x", function(d) { return -d.icon_size/2; })
                    .attr("y", function(d) { return -d.icon_size/2; })
                    .attr("width", function(d) { return d.icon_size; })
                    .attr("height", function(d) { return d.icon_size; })
                d3.select(selectId(d, 'text'))
                    .text(function(d) { return d.domain; })
                    .transition()
                    .attr("y", function(d) { return 2 + d.font_size + d.icon_size/2; })
                    .style("font-size", function(d) { return d.font_size + 'px'; });
                d3.select(selectId(d, 'border'))
                    .transition()
                    .style("fill", "white")
                    .style("stroke", "#555")
                    .style("stroke-width", "1px")
                    .attr("x", function(d) { return -d.icon_size/2; })
                    .attr("y", function(d) { return -d.icon_size/2; })
                    .attr("width", function(d) { return d.icon_size > 32 ? d.icon_size : 0; })
                    .attr("height", function(d) { return d.icon_size; });
            }
        }

        function setCollideRadius() {
            force.force("collide", d3.forceCollide()
                    .radius(function(d) { return 30 +  60 * Math.random(); })
                    .iterations(32))
        }

        function shake(alpha) {
            setCollideRadius();
            force.alpha(alpha).restart();
        }

        function dragstarted(d) {
            shake(0.5);
            d.fx = d.x;
            d.fy = d.y;
        }

        function dragged(d) {
            d.fx = d3.event.x;
            d.fy = d3.event.y;
        }

        function dragended(d) {
            // d.fx = null;
            // d.fy = null;
        }

        force
            .nodes(graph.nodes)
            .force("link").links(graph.links);

        var link = g.selectAll(".link")
            .data(graph.links)
            .enter()
            .append("line")
            .attr("class", "link")
            .style("stroke-width", function(l) { return l.stroke; })
            .style("stroke", function(l) { return l.color; })

        var node = g.selectAll(".node")
            .data(graph.nodes)
            .enter()
            .append("g")
            .attr("class", "node")
            .attr("cursor", "pointer")
            .raise()
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));

        node.append("svg:rect")
            .attr("id", function(d) { return getId(d, 'border'); })
            .style("fill", "white")
            .style("stroke", "#555")
            .style("stroke-width", "1px")
            .attr("x", function(d) { return -d.icon_size/2; })
            .attr("y", function(d) { return -d.icon_size/2; })
            .attr("width", function(d) { return d.icon_size > 32 ? d.icon_size : 0; })
            .attr("height", function(d) { return d.icon_size > 32 ? d.icon_size : 0; })

        node.append("svg:image")
            .attr("id", function(d) { return getId(d, 'icon'); })
            .attr("xlink:href", function(d) { return d.icon; })
            .attr("x", function(d) { return -d.icon_size/2; })
            .attr("y", function(d) { return -d.icon_size/2; })
            .attr("width", function(d) { return d.icon_size; })
            .attr("height", function(d) { return d.icon_size; })
            .on("error", function(d) {
                d.icon_size = 32;
                d3.select(this)
                    .attr("xlink:href", "get?path=icons/browser-web-icon.png")
                    .attr("x", function(d) { return -16; })
                    .attr("y", function(d) { return -16; })
                    .attr("width", function(d) { return 32; })
                    .attr("height", function(d) { return 32; })
                $('#' + getId(d, 'border'))
                    .attr("x", function(d) { return 0; })
                    .attr("y", function(d) { return 0; })
                    .attr("width", function(d) { return 0; })
                    .attr("height", function(d) { return 0; })
            })
            .on("mouseenter", zoomInNode)
            .on("mouseleave", zoomOutNode)

        node.on("mouseenter", function() { d3.select(this).raise(); });

        node.on('mouseover', function(d) {
            link.style('stroke-width', function(l) { return (d === l.source || d === l.target) ? 4 : l.stroke })
                .style('stroke', function(l) { return (d === l.source || d === l.target) ? '#666' : l.color });
        })
        node.on('mouseout', function(d) {
            link.style('stroke-width', function(l) { return l.stroke; })
                .style("stroke", function(l) { return l.color; })
        });

        node.append("text")
            .attr("id", function(d) { return getId(d, 'text'); })
            .attr("x", 0)
            .attr("y", function(d) { return d.image ? 2 + d.font_size + d.icon_size/2 : 7; })
            .style("font-size", function(d) { return d.font_size; })
            .attr("fill", function(d) { return d.color; })
            .text(function(d) { return d.image ? d.domain : d.label; })
            .style("text-anchor", "middle");


        node.on("click", function(d) {
            launch(d.kind, d.label, d.url, d.path);
        });

        force.on("tick", function() {
            link.attr("x1", function(d) { return d.source.x; })
                .attr("y1", function(d) { return d.source.y; })
                .attr("x2", function(d) { return d.target.x; })
                .attr("y2", function(d) { return d.target.y; });

            node.attr("transform", function (d) {
                return "translate(" + d.x + "," + d.y + ")";
            });
        });

        function resize() {
            var width = $(window).width();
            var height = $(window).height();
            if (width != w || height != h) {
                document.location.reload();
            }
        }

        resize();
        d3.select(window).on("resize", resize);
        shake(2);
    });
}

function launch(kind, label, url, path) {
    $(document.body)
        .css('background', 'white')
        .html('<img src="get?path=icons/loading_spinner.gif" class="spinner">');
    switch (kind) {
        case "label":
        case "contact":
            set_preference("query", label);
            document.location = "/?q=" + label;
            break
        case "browser":
        case "google":
            document.location = (url.indexOf('#') == -1) ? url + '##' + query : url;
            break;
        case "file":
        case "gmail":
            document.location = "/get?query=" + localStorage.query + "&path=" + path;
            break;
        default:
            alert('Internal error: Unknown node: ' + kind);
            break;
    }
}

function isNumber(n) {
    return !isNaN(parseFloat(n)) && isFinite(n);
}

$.hasUrlParams = function(name){
    return document.location.href.indexOf('?') != -1;
}

$.urlParam = function(name){
    var results = new RegExp('[\?&]' + name + '=([^&#]*)').exec(document.location.href);
    return results && decodeURI(results[1]) || null;
}

render();
