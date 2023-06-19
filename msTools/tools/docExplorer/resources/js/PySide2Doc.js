// Modifies css (QWebEnginePage.loadFinished)
function updateCss() {
    css = document.createElement('style');
    css.type = 'text/css';
    css.id = 'mrs-style';
    document.head.appendChild(css);

    css.innerText = '\
            .header { display: none; }\
            #footer { display: none; }\
            .main { margin: 0px; width: 100%; max-width: initial; }\
            .main-rounded { padding: 0px !important; }\
            .navigationbar { display: none; }\
            .sphinxsidebar { display: none; }\
            .documentwrapper { margin-left: 0px; }';
}


// Scrolls the document to an anchor location when the page is already loaded
function scrollToAnchor(anchorId) {
    if (document.readyState == 'complete') {
        anchor = document.getElementById(anchorId);
        if (anchor) {
            // anchor.scrollIntoView();
            window.location.hash = "#" + anchorId; // <- Highlights the element
        }
    }
}