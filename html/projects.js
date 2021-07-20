$('#projects').jstree({
    "core" : {
      "animation" : 0,
      "check_callback" : true,
      "themes" : { "stripes" : false },
      "data" : function (obj, callback) {
        $.get("/projects?q=" + localStorage.query, function(data) {
            callback.call(this, JSON.parse(data));
        });
      }
    },
    "types" : {
      "#" : {
        "max_children" : 1,
        "max_depth" : 4,
        "valid_children" : ["root"]
      },
      "root" : {
        "icon" : "icons/keynote-icon.png",
        "valid_children" : ["category"]
      },
      "category" : {
        "valid_children" : ["category", "project"]
      },
      "project" : {
        "icon" : "icons/file-icon.png",
        "valid_children" : []
      }
    },
    "plugins" : [
      "contextmenu", "dnd", "search",
      "state", "types", "wholerow"
    ]
  });