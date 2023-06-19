// Modifies css for base document elements (QWebEnginePage.loadFinished)
function updateBaseCss() {
    css = document.createElement('style');
    css.type = 'text/css';
    css.id = 'mrs-style';
    document.head.appendChild(css);

    css.innerText = '\
        html[data-layout=fixed] .ui-component[data-type=Index] { padding-top: 0px; height: calc(100%); }\
        #ui-header-area { display: none }';
}


// Modifies css for embedded elements (QWebEnginePage.loadProgress is emitted whenever an embedded element is loaded)
function updateEmbeddedCss() {
    function whenReady() {
        iframe = document.getElementById("ui-content-frame");

        if (iframe) {
            iframeDoc = iframe.contentDocument || iframe.contentWindow.document;

            if (iframeDoc.readyState == 'complete') {
                css = document.createElement('style');
                css.type = 'text/css';
                css.id = 'mrs-style-iframe';
                css.innerText = '\
                    #top { display: none }\
                    #side-nav { display: none }\
                    #doc-content { margin-left: 0px !important; height: 100% !important; overflow: initial }';

                iframeDoc.head.appendChild(css);

                // Reparent the license footer (then ignore for subsequent calls)
                footer = jQuery("#ui-footer-area")[0];
                if (footer) {
                    contents = iframeDoc.getElementsByClassName("contents")[0];
                    contents.appendChild(footer);
                }
            }
        }
    }

    if (window.jQuery) {
        // If page is currently loading
        jQuery("#ui-content-frame").on("load", whenReady);
    }
}


// Scrolls the document to an anchor location once the embedded iframe has loaded
function scrollToAnchor(anchorId) {
    function whenReady() {
        iframe = document.getElementById("ui-content-frame");

        if (iframe) {
            iframeDoc = iframe.contentDocument || iframe.contentWindow.document;

            if (iframeDoc.readyState == 'complete') {
                anchor = iframeDoc.getElementById(anchorId);
                if (anchor) {
                    // anchor.scrollIntoView();
                    iframe.contentWindow.location.hash = "#" + anchorId; // <- Highlights the element
                }
            }
        }
    }

    // Wait till required resources have loaded (we must query the embedded document, containing the anchors)
    if (window.jQuery) {
        // If the page is already loaded
        // jQuery("#ui-content-frame").ready(whenReady); // <- Never fires when in Maya
        window.addEventListener('load', whenReady());

        // If page is currently loading (only runs on QWebEnginePage.loadProgress)
        jQuery("#ui-content-frame").on("load", whenReady);
    }
}