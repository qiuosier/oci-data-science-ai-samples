function loadModels(compartmentId, projectId) {
    var container = $("#row-models");
    var spinner = $("#spinner-models");
    spinner.removeClass("d-none");
    $.getJSON("/studio/models?c=" + compartmentId + "&p=" + projectId, function (data) {
        container.html(data.html);
        spinner.addClass("d-none");
    });
}

function loadBuckets() {
    $.getJSON("/storage/buckets?c=" + $("#compartments").val(), function (data) {
        $("#input-storage-namespace").val(data.namespace);

        var dropdown = $("#input-storage-bucket");
        dropdown.empty();
        console.log(data.buckets);
        data.buckets.forEach(element => {
            dropdown.append('<option value="' + element + '">' + element + '</option>');
        })
        dropdown.val(data.buckets[0]);
    });
}

function addModel() {
    var osPath = "oci://" + $("#input-storage-bucket").val() + "@" + $("#input-storage-namespace").val() + "/" + $("#input-storage-prefix").val()
    var modal = bootstrap.Modal.getInstance(document.getElementById('modal-add-model'));
    var compartmentId = $("#compartments").val();
    var projectId = $("#projects").val();
    var data = {
        "model_path": $("#input-model-path").val(),
        "object_storage_path": osPath,
        "compartment_id": compartmentId,
        "project_id": projectId,
    }
    var button = $("#button-add-model");
    button.prop('disabled', true);
    var spinner = $("#spinner-add-model");
    spinner.removeClass("d-none");
    $.ajax({
        type: "POST",
        url: "/studio/models",
        data: JSON.stringify(data),
        contentType: "application/json",
        dataType: 'json',
        success: function (response) {
            spinner.addClass("d-none");
            button.prop('disabled', false);
            modal.hide();
            loadModels(compartmentId, projectId);
        },
        error: function (response) {
            $("#error-add-model").removeClass("d-none").text(response.responseJSON.error);
            spinner.addClass("d-none");
            button.prop('disabled', false);
        }
    });
}