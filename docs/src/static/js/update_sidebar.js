/* 
    Replaces items in the sidebar for the current module based on anchors created by the autobasicsummary directive.
    The following structure will be produced based on existing anchors:
    
    Data
        data0
        data1
    Classes
        Class0
            attribute0
            attribute1
            class0
            class1
            method0
            method1
        Class1
            attribute0
            attribute1
            class0
            class1
            method0
            method1
    Functions
        function0
        function1
*/

function get_anchors(className) {
    paras = Array.from(document.getElementsByClassName(className));
    anchors = paras.map(p => p.getElementsByTagName("a")[0]).filter(a => a != null);
    return anchors;
}


function create_toctree_member(text, level, href) {
    new_li = document.createElement("li");
    new_li.className = "toctree-l" + level.toString();
    new_anchor = document.createElement("a");
    new_anchor.className = "reference internal";
    new_anchor.text = text;
    new_anchor.href = href;
    new_ul = document.createElement("ul");

    new_li.appendChild(new_anchor);
    new_li.appendChild(new_ul);

    return [new_li, new_anchor, new_ul];
}


function create_toctree_member_items(toctree_ul, anchors, level) {
    new_lis = []
    new_anchors = []

    for (let anchor of anchors) {
        span = anchor.getElementsByTagName("span")[0];
        name = span.innerHTML;
        href = anchor.hash;

        new_li = document.createElement("li");
        new_li.className = "toctree-l" + level.toString();
        new_anchor = document.createElement("a");
        new_anchor.className = "reference internal";
        new_anchor.text = name;
        new_anchor.href = href;

        new_li.appendChild(new_anchor);
        toctree_ul.appendChild(new_li);

        new_lis.push(new_li)
        new_anchors.push(new_anchor)
    }

    return [new_lis, new_anchors];
}


function update_sidebar() {
    toctree_li1 = document.getElementsByClassName("toctree-l1 current")[0];

    // The homepage has no current level1 li
    if (toctree_li1 === undefined) {
        return;
    }

    toctree_ul1 = toctree_li1.getElementsByTagName("ul")[0];

    if (toctree_ul1 === undefined) {
        // Create a level1 ul since the current page has no sub-headings
        toctree_ul1 = document.createElement("ul");
        toctree_li1.appendChild(toctree_ul1);
    }
    else {
        // Hide existing level2 li elements from the current level1 ul
        while (toctree_ul1.firstChild) {
            toctree_ul1.removeChild(toctree_ul1.lastChild);
        }
    }

    // Collect anchors
    data_data_anchors = get_anchors("autobasicsummary-data-data");
    attribute_data_anchors = get_anchors("autobasicsummary-attribute-data");
    class_data_anchors = get_anchors("autobasicsummary-class-data");
    method_data_anchors = get_anchors("autobasicsummary-method-data");
    function_data_anchors = get_anchors("autobasicsummary-function-data");
    header_anchors = get_anchors("autobasicsummary-header");

    // Create and populate uls for each member type
    if (data_data_anchors.length) {
        [new_data_title_li, new_data_title_anchor, new_data_title_ul] = create_toctree_member("Data", 2, "#data");
        toctree_ul1.appendChild(new_data_title_li);

        [new_data_lis, new_data_anchors] = create_toctree_member_items(new_data_title_ul, data_data_anchors, 3);
    }

    if (attribute_data_anchors.length || class_data_anchors.length || method_data_anchors.length) {
        [new_classes_title_li, new_classes_title_anchor, new_classes_title_ul] = create_toctree_member("Classes", 2, "#classes");
        toctree_ul1.appendChild(new_classes_title_li);

        // Iterate over all of the attribute and method anchors, adding each anchor to an array which maps to its respective class
        member_mapping = new Map();
        for (let member_data_anchor of [...attribute_data_anchors, ...class_data_anchors, ...method_data_anchors]) {
            qualified_member_name = member_data_anchor.title;
            member_name_tokens = qualified_member_name.split(".");
            qualified_class_name = member_name_tokens.slice(0, -1).join(".");

            if (member_mapping.has(qualified_class_name)) {
                member_mapping.get(qualified_class_name).push(member_data_anchor);
            }
            else {
                member_mapping.set(qualified_class_name, [member_data_anchor]);
            }
        }

        // Sort mapping by header order first if a header exists
        header_anchor_names = header_anchors.map(a => a.title);
        member_mapping = new Map([...member_mapping.entries()].sort((a, b) =>
            (header_anchor_names.indexOf(a[0]) == -1 ? 10000 : header_anchor_names.indexOf(a[0])) -
            (header_anchor_names.indexOf(b[0]) == -1 ? 10000 : header_anchor_names.indexOf(b[0]))
        ));

        for (let [qualified_class_name, member_data_anchors] of member_mapping) {
            member_name_tokens = qualified_class_name.split(".");
            class_name = member_name_tokens[member_name_tokens.length - 1];
            [new_class_title_li, new_class_title_anchor, new_class_title_ul] = create_toctree_member(class_name, 3, "#" + qualified_class_name);
            new_classes_title_ul.appendChild(new_class_title_li);

            [new_class_lis, new_class_anchors] = create_toctree_member_items(new_class_title_ul, member_data_anchors, 4);
        }
    }

    if (function_data_anchors.length) {
        [new_functions_title_li, new_functions_title_anchor, new_functions_title_ul] = create_toctree_member("Functions", 2, "#functions");
        toctree_ul1.appendChild(new_functions_title_li);

        [new_function_lis, new_function_anchors] = create_toctree_member_items(new_functions_title_ul, function_data_anchors, 3);
    }
}


// Run directly after DOM is ready
$(document).ready(update_sidebar);
