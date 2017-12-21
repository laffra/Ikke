const NORMAL_ICON_SIZE = 32;

var search_finished = {};

var RENDER_AS_GRID = localStorage.rendertype == 'grid';
var TOP_HEIGHT = 250;

var ALPHA_INITIAL = 0.5
var ALPHA_WARMUP = 0.05
var ALPHA_SHAKE = 0.1
var ALPHA_DRAG = 0.1
var ALPHA_WARMUP_COUNT = 7

function init_tabs() {
    $('#tabs')
        .tabs({
            active : localStorage.getItem('tab', 0),
            activate : function(event, ui) {
                if (ui.newTab.attr('remember') == 'true') {
                    render_tab(localStorage.tab = ui.newTab.parent().children().index(ui.newTab));
                }
            }
        })
        .css('display', 'block')
    $('#google').click(search_google);
    $('#settings').click(settings);
    $('#main').css('display', 'block')
    $('.tab-contents').width(window.innerWidth - 2 * $('.logo').width() - 96);

}

function rerender(kind) {
    size_selects();
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

    window.onpopstate = function(e){
        if (e.state) {
            document.getElementById("query").value = e.state;
            document.title = e.state.pageTitle;
        }
    };

    $.get("search?" + get_args(query, ''), function() {
        d3.range(kinds.length).forEach(function(index) {
            if (index == localStorage.tab) {
                render_tab(index);
            }
        })
    });

}

function render_tab(index) {
    var w = window.innerWidth;
    var h = window.innerHeight;
    var kind = kinds[index];
    $("#tabs-" + kind + ' svg').remove();
    setTimeout(function() {
        if (!search_finished[kind]) {
            $(".spinner")
                .css("margin-left", w/3)
                .css("margin-top", h/4)
                .css("display", "block");
        }
    }, 500);
    if (RENDER_AS_GRID) {
        load_grid(kind, w, h - TOP_HEIGHT);
    } else {
        load_graph(kind, w, h - TOP_HEIGHT);
    }
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
    search_finished[kind] = true;
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
        day: 'one day',
        week: 'one week',
        month: 'one month',
        month3: 'three months',
        month6: 'six months',
        year: 'one year',
        forever: 'forever'
    }[get_preference("duration") || 'month'];

    var count = graph.nodes.filter(function(node) { return node.kind != 'label'; }).length;
    var stats = JSON.parse(graph.stats);
    var removed = !stats.removed ? '' :
        ', with <a href=# class="removed-' + kind + '">' + stats.removed + ' similar results</a> removed,';
    $('#summary-' + kind).append(
        $('<span>').text('Showing ' + count + ' results for '),
        $('<span>')
            .addClass('select-wrapper')
            .append($('<select>')
                .attr('id', 'duration-' + kind)
                .on('change', function() { rerender(kind); })
                .append([
                    $('<option>').attr('value', 'day').text('one day'),
                    $('<option>').attr('value', 'week').text('one week'),
                    $('<option>').attr('value', 'month').text('one month'),
                    $('<option>').attr('value', 'month3').text('three months'),
                    $('<option>').attr('value', 'month6').text('six months'),
                    $('<option>').attr('value', 'year').text('one year'),
                    $('<option>').attr('value', 'forever').text('forever'),
                ])
                .val(get_preference('duration', 'month'))),
        $('<span>')
            .html(removed),
        $('<span>')
            .text(' as a '),
        $('<span>')
            .addClass('select-wrapper')
            .append($('<select>')
                .addClass('filter')
                .attr('id', 'rendertype-' + kind)
                .on('change', function() { rerender(kind); })
                .append([
                    $('<option>').attr('value', 'graph').text('graph'),
                    $('<option>').attr('value', 'grid').text('grid'),
                ])
                .val(get_preference('rendertype', 'graph'))),
    );
    $('.removed-' + kind).click(show_duplicates);

    if (get_preference('rendertype', 'graph') === "graph") {
        $(".zoom-buttons")
            .css('display', "inline-block");
    }
    $('#node-count').text('N:' + graph.nodes.length);
    size_selects();
}

function load_graph(kind, w, h) {
    var force = d3.forceSimulation()
            .force("link", d3.forceLink().distance(10).strength(3))
            .force("x", d3.forceX(w/2).strength(0.3))
            .force("y", d3.forceY(h/2).strength(2.5))
            .force("charge", d3.forceManyBody().strength(1))
            .alpha(ALPHA_INITIAL)
            .alphaDecay(0.05);

    var w = $(window).width();
    var h = $(window).height() - TOP_HEIGHT;
    var zoom = d3.zoom().scaleExtent([0.3, 2]).on("zoom", zoomed);
    var svg = d3.select("#tabs-" + kind)
        .append("svg")
        .style("cursor", "move")
        .call(zoom);
    var g = svg.append("g");
    var current_zoom_scale = 0.9;
    zoom.scaleTo(svg, current_zoom_scale);

    function zoomed(a, b, c) {
        current_zoom_scale = d3.event.transform.k;
        g.style("stroke-width", 1.5 / d3.event.transform.k + "px");
        g.attr("transform", d3.event.transform);
        $('#zoom-scale').text('Z:' + current_zoom_scale);
    }

    d3.selectAll('#zoom-in-' + kind).on('click', function() {
        zoom.scaleTo(svg, current_zoom_scale *= 1.3);
    });

    d3.selectAll('#zoom-out-' + kind).on('click', function() {
        zoom.scaleTo(svg, current_zoom_scale *= 0.7);
    });

    d3.json("graph?" + get_args(query, kind), function(error, graph) {
        svg.attr("width", w - 2 * $('.logo').width() - 96)
           .attr("height", h + TOP_HEIGHT);
        clear_spinner(kind, error, graph);

        update_summary(kind, graph);

        zoom.scaleTo(svg, current_zoom_scale = Math.min(1, Math.min(w,h)/graph.nodes.length/15));
        force.alphaDecay(Math.max(0.05, graph.nodes.length/1000));

        svg.insert("rect", ":first-child")
            .attr("id", "background-" + kind)
            .attr("fill", 'white')
            .attr("width", w)
            .attr("height", h)
            .on("click", function() { shake(ALPHA_SHAKE); });
        setCollideRadius();

        var nodeById = {}
        d3.range(graph.nodes.length).forEach(function(index) { nodeById[index] = graph.nodes[index] });

        graph.nodes.forEach(function(d) {
            d.vx = 3;
            d.vy = 0.1
        });

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
                        console.log('"' + d.url + '"');
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
                    .text(function(d) { return d.label; })
                    .transition()
                    .attr("y", function(d) { return d.font_size + d.icon_size/2; })
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
            shake(ALPHA_DRAG);
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
                d3.select(selectId(d, 'text'))
                    .attr("y", function(d) { return d.font_size + d.icon_size/2 - 2; })
                    .style("font-size", function(d) { return d.font_size + 'px'; });
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
            .attr("y", function(d) { return d.icon_size ? d.font_size + d.icon_size/2 - 2 : d.font_size/2; })
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

        function warmup() {
            d3.range(ALPHA_WARMUP_COUNT).forEach(function() {
                force.alpha(ALPHA_INITIAL);
                while (force.alpha() > ALPHA_WARMUP) {
                    force.tick();
                }
            })
            shake(ALPHA_WARMUP);
        }

        function resize() {
            var width = $(window).width();
            var height = $(window).height() - TOP_HEIGHT;
            if (Math.abs(width - w) > 100 || Math.abs(height - h) > 100) {
                document.location.reload();
            }
        }

        resize();
        d3.select(window).on("resize", resize);
        warmup();
    });
}

function launch(kind, label, url, path) {
    function replace(url) {
        $(document.body)
            .css('background', 'white')
            .html('<img src="get?path=icons/loading_spinner.gif" class="spinner">');
        document.location = url;
    }
    switch (kind) {
        case "label":
        case "contact":
            set_preference("query", label);
            replace("/?q=" + label);
            break
        case "browser":
        case "google":
            replace(url);
            break;
        case "file":
        case "gmail":
            window.open("/get?query=" + localStorage.query + "&path=" + path);
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

function size_selects() {
    $('select').each(function() {
        var span = $("<span>")
            .text($(this).find("option:selected").text())
            .css('font-size', $(this).css('font-size'))
            .css("visibility", "hidden")
            .appendTo($(this).parent());
        $(this).width(span.width());
        span.remove();
    });
}

render();
