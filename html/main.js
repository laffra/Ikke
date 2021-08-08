const NORMAL_ICON_SIZE = 32;

var search_finished = {};

var RENDER_AS_GRID = localStorage.rendertype == 'grid';
var TOP_HEIGHT = 250;
var LEFT_MARGIN = 350;

var ALPHA_INITIAL = 0.5
var ALPHA_SHAKE = 0.05
var ALPHA_DRAG = 0.01
var ALPHA_DRAG_START = 0.01

var LINK_DISTANCE = 20
var LINK_STRENGTH = 5
var NODE_RADIUS = 50
var LINE_WIDTH_RATIO = 1.3

var COLLIDE_ITERATIONS = 2
var FORCE_CENTER_X = 0.1
var FORCE_CENTER_Y = 1.0
var NODE_FONT_SIZE = 24
var SPECIAL_NODE_FONT_SIZE = 28
var IMAGE_SIZE_MINIMUM = 7
var IMAGE_SIZE_RATIO = 1

var altKeyPressed = false;

$(document).keydown(function(event){
    altKeyPressed = event.altKey;
});
$(document).keyup(function(){
    altKeyPressed = false;
});

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

function hide_duplicates() {
    document.location = "/?q=" + localStorage.query;
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

    run_query(query);
}

function run_query(query) {
    var email = $("#ikke-search-email").text();
    $(".spinner")
        .css("margin-left", window.innerWidth/3)
        .css("margin-top", window.innerHeight/4)
        .css("display", "block");
    if (!email) {
        setTimeout(() => run_query(query), 10);
    } else {
        $.get("search?email=" + email + "&" + get_args(query, ''), function() {
            d3.range(kinds.length).forEach(function(index) {
                if (index == localStorage.tab) {
                    render_tab(index);
                }
            })
        });
    }

}

function render_tab(index) {
    var w = window.innerWidth;
    var h = window.innerHeight;
    var kind = kinds[index];
    $("#tabs-" + kind + ' svg').remove();
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
            $('#tabs-' + kind + ' .ui-table').remove()
            var table = $('<table class="ui-table">').appendTo($('#tabs-' + kind + ' .tab-contents'));
            table.append($('<tr>').append([
                $('<th colspan=2 width=630>').text('Title'),
                $('<th width=70>').text('Date'),
                $('<th width=400>').text('Who'),
            ]));
        }
        var sorted_nodes = graph.nodes.sort(function compare(a, b) {
            return a.timestamp < b.timestamp ? 1 : -1;
        });
        function get_icon(node) {
            return node.kind == 'contact' ? 'get?path=icons/person-icon.png' : node.icon;
        }
        $.each(sorted_nodes, function(index, node) {
            if (node.kind == kind || (kind == 'all' && node.kind != 'label')) {
                table.append($('<tr>')
                    .on("click", function() {
                        var row = $(this);
                        launch(node);
                    })
                    .attr('kind', node.kind)
                    .attr('label', node.label)
                    .attr('url', node.url)
                    .attr('path', node.path)
                    .append([
                        $('<td width=10>').append(
                            $('<img class="grid-icon">').attr('src', get_icon(node)).css('width', '16px')
                        ),
                        $('<td width=600>').html(node.url || node.subject || (node.kind == 'contact' ? '<i>Contact:</i> ' : ' ') + node.label),
                        $('<td>').html(nobreaks((node.date || '').split(' ')[0])),
                        $('<td width=400>').html(nobreaks(node.persons.map(x => x.label).join(', ')))
                        ]));
                } else {
                console.log('skip grid: ' + node.kind + ' ' + node.label)
                }
            })
            $('.grid-icon').on('error', function() {
                $(this).attr('src', "get?path=icons/browser-web-icon.png");
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
    var stats = graph.stats;
    var action = stats.removed
        ? '. There is more: <a href=# class="removed-' + kind + '">Show ' + stats.removed + ' similar results</a>.'
        : '. Zoom out: <a href=# class="included-' + kind + '">Remove duplicate results</a>.';
    $('#summary-' + kind).empty().append(
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
        $('<span>')
            .html(action),
    );
    $('.removed-' + kind).click(show_duplicates);
    $('.included-' + kind).click(hide_duplicates);

    if (get_preference('rendertype', 'graph') === "graph") {
        $(".zoom-buttons")
            .css('display', "inline-block");
    }
    $('#dashboard-node-count').text('Count:' + graph.nodes.length);
    size_selects();
}

function linkDistance(link) {
    const distance = LINK_DISTANCE
    return isTimeLink(link) ? 2 * distance : distance;
}

function isTimeLink(link) {
    return (link.source.kind == 'time' || link.target.kind == 'time');
}

function linkStrength(link) {
    return isTimeLink(link) ? 5 * LINK_STRENGTH : LINK_STRENGTH;
}

function linkColor(link) {
    return isTimeLink(link) ? "#BBB" : link.color;
}

function linkWidth(link) {
    return isTimeLink(link) ? 1 : 2;
}

function load_graph(kind, w, h) {
    var force = d3.forceSimulation()
            .force("link", d3.forceLink().distance(linkDistance).strength(linkStrength))
            .force("x", d3.forceX(w / 2 - 300).strength(FORCE_CENTER_X))
            .force("y", d3.forceY(h / 2).strength(FORCE_CENTER_Y))
            .force("charge", d3.forceManyBody().strength(5))
            .alpha(ALPHA_INITIAL)
            .alphaDecay(0.1);

    var zoom = d3.zoom().scaleExtent([0.3, 2]).on("zoom", zoomed);
    var svg = d3.select("#tabs-" + kind)
        .append("svg")
        .style("cursor", "move")
        .call(zoom);
    var g = svg.append("g");
    var current_zoom_scale = 7;
    zoom.scaleTo(svg, current_zoom_scale);

    function zoomed(a, b, c) {
        current_zoom_scale = d3.event.transform.k;
        g.style("stroke-width", 1.5 / d3.event.transform.k + "px");
        g.attr("transform", d3.event.transform);
        $('#dashboard-zoom-scale').text('Zoom:' + Number(current_zoom_scale).toFixed(2));
    }

    d3.selectAll('#zoom-in-' + kind).on('click', function() {
        zoom.scaleTo(svg, current_zoom_scale *= 1.3);
    });

    d3.selectAll('#zoom-out-' + kind).on('click', function() {
        zoom.scaleTo(svg, current_zoom_scale *= 0.7);
    });

    console.log("Loading graph");
    graph_start = new Date().getTime();
    d3.json("graph?" + get_args(query, kind), function(error, graph) {
        function getTimeNodes() {
            return graph.nodes.filter(d => d.uid.startsWith("time-"))
                .sort(function(d1, d2) {
                    return d1.index - d2.index;
                });
        }

        graph_loaded = new Date().getTime();
        svg.attr("width", w - 2 * $('.logo').width() - 96)
           .attr("height", h + TOP_HEIGHT);
        clear_spinner(kind, error, graph);
        $('#dashboard-memory').text('Memory:' + graph.stats.memory);
        $('#dashboard-results').text('Total:' + (graph.stats.results || 0));
        $('#dashboard-search-time').text('Duration:' + Number((graph.stats.search_time || 0)).toFixed(1) + 's');
        $('#dashboard-files').text('Files:' + (graph.stats.files || 0));
        update_summary(kind, graph);

        zoom.translateBy(svg, -LEFT_MARGIN, -TOP_HEIGHT);
        zoom.scaleTo(svg, current_zoom_scale = Math.min(0.6, w/graph.nodes.length/37));
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

        graph.nodes.forEach(function(d, index) {
            d.vx = 3;
            d.vy = 1;
        });
        const timeNodes = getTimeNodes();
        const timeSpace = Math.sqrt(Math.sqrt(Math.sqrt(graph.nodes.length))) * w / timeNodes.length;
        timeNodes.forEach(function(d, index) {
                d.fx = index * timeSpace;
                d.fy = h/2 - 200 + 400 * (index % 2);
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
            if (d.kind === 'label' && d.kind !== 'time') return;
            d3.select(selectId(d, 'border'))
                .transition()
                .style("stroke", "#ddd")
                .style("stroke-width", "2px")
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
            d3.select(this.parentNode).raise();
        }

        function zoomInLabel(d) {
            if (d.kind !== 'label' && d.kind !== 'time') return;
            d3.select(selectId(d, 'text'))
                .transition()
                .attr("fill", function(d) { return 'black'; })
                .style("font-size", function(d) { return 2 * Math.max(16, d.font_size) + 'px'; })
        }

        function zoomOutNode(d) {
            if (d.kind === 'label' && d.kind !== 'time') return;
            d3.select(this)
                .transition()
                .duration(1000)
                .attr("x", function(d) { return -d.icon_size/2; })
                .attr("y", function(d) { return -d.icon_size/2; })
                .attr("width", function(d) { return d.icon_size; })
                .attr("height", function(d) { return d.icon_size; })
            d3.select(selectId(d, 'text'))
                .transition()
                .duration(500)
                .attr("y", function(d) { return d.font_size + d.icon_size/2; })
                .style("font-size", 0)
            setTimeout(function() {
                d3.select(selectId(d, 'text'))
                    .transition()
                    .duration(100)
                    .text(function(d) { return d.label; })
                    .style("font-size", function(d) { return d.font_size + 'px'; });
            }, 500);
            d3.select(selectId(d, 'border'))
                .transition()
                .duration(1000)
                .style("stroke-width", "1px")
                    .attr("x", function(d) { return -d.icon_size/2; })
                    .attr("y", function(d) { return -d.icon_size/2; })
                    .attr("width", function(d) { return d.icon_size > 32 ? d.icon_size : 0; })
                    .attr("height", function(d) { return d.icon_size; });
        }

        function zoomOutLabel(d) {
            if (d.kind !== 'label' && d.kind !== 'time') return;
            d3.select(selectId(d, 'text'))
                .transition()
                .attr("fill", function(d) { return d.color; })
                .style("font-size", function(d) { return d.font_size + 'px'; })
        }

        function setCollideRadius() {
            force.force("collide", d3.forceCollide()
                    .radius(NODE_RADIUS)
                    .iterations(18))
        }

        function shake(alpha) {
            setCollideRadius();
            force.alpha(alpha).restart();
        }

        function dragstarted(d) {
            shake(ALPHA_DRAG_START);
            d.fx = d.x;
            d.fy = d.y;
        }

        function dragged(d) {
            d.fx = d.tx = d3.event.x;
            d.fy = d.ty = d3.event.y;
            shake(ALPHA_DRAG);
        }

        function dragended(d) {
            shake(ALPHA_DRAG);
        }

        force
            .nodes(graph.nodes)
            .force("link").links(graph.links);

        var link = g.selectAll(".link")
            .data(graph.links)
            .enter()
            .append("line")
            .attr("class", "link")
            .style("stroke-opacity", 0.25)
            .style("stroke-width", linkWidth)
            .style("stroke", linkColor)

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
            .style("stroke", "#ddd")
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

        node.on("mouseenter", function() {
            d3.select(this).raise();
        });

        node.on('mouseenter', function(d) {
            link.transition()
                .duration(300)
                .style('stroke-opacity', function(l) { return (d === l.source || d === l.target) ? 1 : 0.25 })
                .style('stroke-width', function(l) {
                    if (d === l.source || d === l.target) {
                        return 4;
                    }
                    return linkWidth(l);
                })
                .style('stroke', function(l) { return (d === l.source || d === l.target) ? '#666' : linkColor(l) });
        })
        node.on('mouseout', function(d) {
            link.transition()
                .duration(1000)
                .style('stroke-opacity', 0.25)
                .style("stroke-width", linkWidth)
                .style("stroke", linkColor)
        });

        node.append("text")
            .attr("id", function(d) { return getId(d, 'text'); })
            .attr("x", 0)
            .attr("y", function(d) { return d.icon_size ? d.font_size + d.icon_size/2 - 2 : d.font_size/2; })
            .style("font-size", function(d) { return d.font_size; })
            .attr("fill", function(d) { return d.color; })
            .text(function(d) { return d.image ? d.domain : d.label; })
            .style("text-anchor", "middle")
            .on("mouseenter", zoomInLabel)
            .on("mouseleave", zoomOutLabel);


        node.on("click", function(d) {
            if (altKeyPressed) {
                console.log(d);
                console.log(d.uid);
            } else {
                launch(d);
            }
        });

        force.on("tick", function() {
            node.attr("transform", function (d) {
                return "translate(" + d.x + "," + d.y + ")";
            });

            link.attr("x1", function(d) { return d.source.x; })
                .attr("y1", function(d) { return d.source.y; })
                .attr("x2", function(d) { return d.target.x; })
                .attr("y2", function(d) { return d.target.y; });
        });

        function resize() {
            var width = $(window).width();
            var height = $(window).height() - TOP_HEIGHT;
            if (Math.abs(width - w) > 100 || Math.abs(height - h) > 100) {
                document.location.reload();
            }
        }

        d3.select(window).on("resize", resize);
        graph_rendered = new Date().getTime();
        console.log("GRAPH loaded", graph_loaded - graph_start)
        console.log("GRAPH rendered", graph_rendered - graph_start)
    });
}

function launch(obj) {
    switch (obj.kind) {
        case "file":
            open_file(obj);
            break;
        case "label":
            document.location = "/?q=" + obj.label;
            break;
        default:
            render_in_window(obj);
    } 
}

function open_file(obj) {
    console.log("Open", obj);
    var email = $("#ikke-search-email").text();
    $.get("open?email=" + email + "&path=" + obj["path"], function() {
        console.log("Opened", obj);
    });
}

function render_in_window(obj) {
    const protocol = window.location.protocol;
    const host = window.location.hostname;
    const port = window.location.port;
    var url = protocol + "//" + host + ":" +  port + "/render?query=" + localStorage.query;
    Object.keys(obj).forEach(function(key,index) {
        url += "&" + key + "=" + encodeURIComponent(obj[key]);
    });
    window.open(url);
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
