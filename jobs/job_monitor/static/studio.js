function loadModels(compartmentId, projectId) {
    var container = $("#row-models");
    var spinner = $("#spinner-models");
    spinner.removeClass("d-none");
    $.getJSON("/studio/models?c=" + compartmentId + "&p=" + projectId, function (data) {
        container.html(data.html);
        spinner.addClass("d-none");
    });
}