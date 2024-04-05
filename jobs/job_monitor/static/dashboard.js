// The following intervals are in milliseconds
// Interval for checking new jobs
const JOB_CHECKING_INTERVAL = 20000;
// Interval for updating logs of each job run
const LOG_CHECKING_INTERVAL = 20000;
// Interval for checking new job runs
const RUN_CHECKING_INTERVAL = 30000;
var jobRunChecking = {};


function getUrlParam(name) {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get(name);
}

function showAuthenticationAlert(data) {
  $("#alert-authentication").removeClass("d-none").find("span").text(data.message);
}


function getJSON(url, parameters, success_callback, error_callback) {
  var dropdown = $("#profile");
  if (dropdown.children('option').length > 0) {
    parameters["profile"] = dropdown.val();
  } else {
    profile = getUrlParam("profile");
    if (profile != null) parameters["profile"] = profile;
  }

  url = url + "?" + $.param(parameters);
  // console.log(url);
  return $.ajax({
    type: "GET",
    url: url,
    contentType: "application/json",
    dataType: 'json',
    success: success_callback,
    error: function (xhr) {
      if (xhr.status === 0) toastMessage("Connection Error", "Check Backend App and Connection.")
      if (xhr.status === 401) showAuthenticationAlert(xhr.responseJSON);
      if (error_callback !== undefined && xhr.responseJSON !== undefined) error_callback(xhr.responseJSON);
      else console.error(xhr);
    }
  })
  //return $.getJSON(url, success_callback).error();
}

function postJSON(url, data, success_callback, error_callback) {
  return $.ajax({
    type: "POST",
    url: url,
    data: JSON.stringify(data),
    contentType: "application/json",
    dataType: 'json',
    success: success_callback,
    error: error_callback
  })
}

function switchProfile(data) {
  console.log(data);
  if (data.profile !== null) {
    var href = new URL(window.location.href);
    href.searchParams.set('profile', data.profile);
    if (data.compartment_id != null) href.searchParams.set('c', data.compartment_id);
    if (data.project_id != null) href.searchParams.set('p', data.project_id);
    window.location.replace(href.toString());
  }
}

function initWithProfile(callback) {
  var dropdown = $("#profile");
  getJSON("/profiles", {}, function (data) {

    if (data.profiles.length > 0) {
      data.profiles.forEach(element => {
        if (element === data.profile) {
          dropdown.append('<option value="' + element + '" selected>' + element + '</option>');
        } else {
          dropdown.append('<option value="' + element + '">' + element + '</option>');
        }
      });
      const urlParams = new URLSearchParams(window.location.search);
      const profile = urlParams.get('profile');

      if (profile != data.profile && data.profile !== null) {
        switchProfile(data);
      }
      console.log("Using profile: " + profile)
      dropdown.change(function () {
        postJSON("/profiles", { "profile": dropdown.val() }, switchProfile)
      });
    };
    initComponents(callback);
  });

}

// This function is use to check if the authentication is done.
function checkTenancy() {
  getJSON(
    "/tenancy",
    {},
    function (data) {
      if (data.error == null) {
        // Refresh the page to load the list of compartments.
        document.location.reload();
      }
    },
    function () {
      // Check again in a few seconds.
      setTimeout(function () {
        checkTenancy();
      }, 10000);
    }
  )
}

function initJobMonitor() {
  // Load jobs
  var compartmentDropdown = $("#compartments");
  var compartmentId = compartmentDropdown.val();
  var projectId = $("#project_ocid").text();
  if (compartmentId && projectId != "None") {
    loadJobs(compartmentId, projectId);
  } else if (compartmentDropdown.children('option').length == 0) {
    checkTenancy();
  }
}

function initComponents(callback) {
  var compartmentDropdown = $("#compartments");
  var projectDropdown = $("#projects");
  var compartmentId = compartmentDropdown.val();
  var projectId = $("#project_ocid").text();
  console.log("COMPARTMENT ID: " + compartmentId);
  console.log("PROJECT ID: " + projectId);

  console.log(compartmentDropdown.children('option').length);
  console.log(projectDropdown.children('option').length);

  if (typeof callback === 'function') {
    callback();
  } else {
    console.log("Init callback is not a function.");
  }

  // Load the list of project in the compartment.
  compartmentDropdown.change(function () {
    var ocid = compartmentDropdown.val();
    if (ocid === "") return;
    getJSON("/projects/" + ocid, {}, function (data) {
      projectDropdown.empty();
      // console.log(projectId);
      if (projectId == "None" || projectId == "all") {
        projectDropdown.append('<option value="" selected="selected">Select Project</option>');
      }
      var projectIdValid = false;
      data.projects.forEach(element => {
        if (element.ocid === projectId) {
          projectDropdown.append('<option value="' + element.ocid + '" selected>' + element.display_name + '</option>');
          projectIdValid = true;
        } else {
          projectDropdown.append('<option value="' + element.ocid + '">' + element.display_name + '</option>');
        }
      });
      if (!projectIdValid) {
        $("#project_ocid").text("Invalid")
        toastMessage("Invalid Project ID", "Project is not found in the compartment.");
      }
    })
  })
  // Trigger the compartment change callback to load the list of projects.
  if (compartmentId) compartmentDropdown.change();
  // Refresh the page to when project is changed.
  projectDropdown.change(function () {
    projectId = projectDropdown.val();
    if (projectId === "") return;
    compartmentId = compartmentDropdown.val();
    var url = new URL(window.location.href);
    url.searchParams.set('c', compartmentId);
    url.searchParams.set('p', projectId);
    window.location.href = url.toString();
  });
}

function updateLogs(ocid, outputDiv, stopped) {
  // console.log("Getting logs for " + ocid);
  // Get the most recent logs of each job
  getJSON("/logs/" + ocid, {}, function (data) {
    // console.log($("#" + ocid));
    var ansiUp = new AnsiUp;
    var htmlLogs = ansiUp.ansi_to_html(data.logs.join("\n"));
    outputDiv.html(htmlLogs);
    // Scroll to the bottom
    outputDiv.scrollTop(outputDiv[0].scrollHeight);
    parent = outputDiv.closest(".card");
    statusText = parent.find(".run-status");
    statusText.text(data.status);
    statusDetailsText = parent.find(".run-status-details");
    if (data.statusDetails !== null) {
      statusDetailsText.text(data.status + " - " + data.statusDetails);
    } else {
      statusDetailsText.text(data.status);
    }
    updateMetrics(ocid);
    // If stopped is set to true, no further update will be performed.
    if (stopped === true) return;

    if (data.stopped !== true) {
      // Job is running
      setTimeout(function () {
        updateLogs(ocid, outputDiv);
      }, LOG_CHECKING_INTERVAL);
      setCardStyle(parent, "border-primary");
      statusText.addClass("text-primary");
      parent.find(".card-header").addClass("bg-primary bg-opacity-10");
    } else {
      // Job terminated
      if (data.status === "SUCCEEDED") {
        setCardStyle(parent, "border-success");
        statusText.addClass("text-success");
        parent.find(".card-header").addClass("bg-success text-success bg-opacity-10");
      } else if (data.status === "FAILED") {
        setCardStyle(parent, "border-danger");
        statusText.addClass("text-danger");
        parent.find(".card-header").addClass("bg-danger text-danger bg-opacity-10");
      }
      // When job run is stop, there might be logs still being processed by the OCI logging service
      // Here we check the logs after some intervals hoping we can get all the logs.
      setTimeout(function () {
        updateLogs(ocid, outputDiv, true);
      }, LOG_CHECKING_INTERVAL);
      setTimeout(function () {
        updateLogs(ocid, outputDiv, true);
      }, LOG_CHECKING_INTERVAL * 2);
      setTimeout(function () {
        updateLogs(ocid, outputDiv, true);
      }, LOG_CHECKING_INTERVAL * 3);
    }
  })
}

function setCardStyle(card, borderClass) {
  card.removeClass("border-primary");
  card.addClass(borderClass);
}

function deleteResource(ocid) {
  var serviceEndpoint = $("#service-endpoint").text();
  $.getJSON("/delete/" + ocid + "?endpoint=" + serviceEndpoint, function (data) {
    console.log("Deleting: " + ocid);
    if (data.error === null) {
      $("#" + ocid.replace(/\./g, "")).remove();
    } else {
      alert(data.error);
    }
  });
}

function loadJobs(compartmentId, projectId) {
  var limit = $("#job-number-limit").text();
  var existing_jobs = $("#dashboard-jobs .accordion-item .job-ocid").map(function () {
    return $(this).text();
  }).get();
  var apiEndpoint = "/jobs/" + compartmentId + "/" + projectId;

  getJSON(
    apiEndpoint,
    { "limit": limit },
    function (data) {
      $("#alert-authentication").addClass("d-none");
      var timestampDiv = $("#dashboard-jobs").find(".job-timestamp:first");
      var timestamp = 0;
      var jobs = data.jobs;
      // No job found
      if (jobs.length === 0) {
        // Wait for the projects dropdown to be populated so that we can get the project name.
        setTimeout(() => {
          var compartmentName = $("#compartments option[value='" + compartmentId + "']").text();
          var projectName = $("#projects option[value='" + projectId + "']").text();
          console.log("No job found in compartment: " + compartmentId + ", project: " + projectId);
          toastMessage("No Job", "There is no job in " + compartmentName + "/" + projectName);
        }, 2000);
        return;
      }
      var prepended = false;
      if (timestampDiv.length !== 0) {
        timestamp = parseFloat(timestampDiv.text())
        jobs = jobs.reverse();
      }
      // Add jobs based on the time created
      jobs.forEach(job => {
        if (existing_jobs.indexOf(job.ocid) < 0 && job.time_created > timestamp) {
          console.log("Loading job: " + job.ocid);
          if (timestamp > 0) {
            $("#dashboard-jobs").prepend(job.html);
            prepended = true;
          } else {
            $("#dashboard-jobs").append(job.html);
          }
          // Load job runs only when the accordion is opened.
          $('#' + job.ocid.replaceAll(".", "")).on('shown.bs.collapse', function (e) {
            if ($(e.target).hasClass("accordion-job")) checkAndLoadJobRuns(job.ocid);
          })
        }
      });
      // Open the first accordion in the page
      // If user is opening loading the jobs for the first time or new job added recently
      if (existing_jobs.length === 0 || prepended) {
        new bootstrap.Collapse(
          document.getElementsByClassName('accordion-collapse collapse')[0],
          { toggle: true }
        );
      }
    },
    function (data) {
      if (data.error == 401) {
        $("#alert-authentication").removeClass("d-none").find("span").text(data.message);
      } else {
        toastMessage(data.error, data.message);
      }
    }
  );
  // Reload the list of jobs every 20 seconds.
  setTimeout(function () {
    loadJobs(compartmentId, projectId);
  }, JOB_CHECKING_INTERVAL);
}

// Create a new chart
function newChart(ctx, labels, datasets) {
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true
        },
        x: {
          display: false
        }
      }
    }
  });
}

// Check if two datasets are containing the same values
function compareDatasets(ds1, ds2) {
  if (ds1.length !== ds2.length) return false;
  for (let i = 0; i < ds1.length; i++) {
    if (ds1[i].label !== ds2[i].label) return false;
    if (JSON.stringify(ds1[i].data) !== JSON.stringify(ds2[i].data)) return false;
  }
  return true;
}

// Merge the metric data with the data in the existing chart
function mergeChartData(chart, data) {
  const existingLabels = JSON.stringify(chart.data.labels);
  // Return if labels and datasets are the same
  if (existingLabels == JSON.stringify(data.timestamps) && compareDatasets(chart.data.datasets, data.datasets)) return;
  const existingLength = chart.data.labels.length;
  // Check if we only need to append new data
  // Appending data will avoid refreshing the entire chart
  var appendData = true;
  if (existingLabels == JSON.stringify(data.timestamps.slice(0, existingLength)) && chart.data.datasets.length == data.datasets.length) {
    for (let i = 0; i < chart.data.datasets.length; i++) {
      if (JSON.stringify(chart.data.datasets[i].data) != JSON.stringify(data.datasets[i].data.slice(0, existingLength))) {
        appendData = false;
      }
    }
  } else {
    appendData = false;
  }
  if (appendData) {
    // Append data
    for (let i = existingLength; i < data.timestamps.length; i++) {
      chart.data.labels.push(data.timestamps[i]);
      for (let j = 0; j < chart.data.datasets.length; j++) {
        chart.data.datasets[j].data.push(data.datasets[j].data[i]);
      }
    }
  } else {
    // Replace data
    // This will refresh the entire chart
    chart.data.labels = data.timestamps;
    chart.data.datasets = data.datasets;
  }

  chart.update();
}

// Check if there are new metric data and update the metric chart
function updateMetrics(ocid) {
  const canvasId = "metrics-" + ocid.replaceAll(".", "");
  const ctx = document.getElementById(canvasId);
  if (ctx === null) return;
  // Find the name of the metric currently being displayed.
  const metricName = $(ctx).closest(".job-run-metrics").find(".dropdown-menu .d-none a").data("val");
  getJSON("/metrics/" + metricName + "/" + ocid, {}, function (data) {
    // Refresh the list of the metrics
    const metricDropdown = $(ctx).closest(".job-run-metrics").find(".dropdown-menu");
    $.each(data.metrics, function (i, metric) {
      if (metricDropdown.find("[data-val='" + metric.key + "']").length == 0) {
        metricDropdown.append('<li><a class="dropdown-item" data-val="' + metric.key + '" href="#">' + metric.display + '</a></li>');
      }
    })
    var chart = Chart.getChart(canvasId);
    if (chart === undefined) {
      // Create a new chart
      // this is called when the panel is initialized for the first time
      newChart(ctx, data.timestamps, data.datasets);
    } else {
      // Update the data for the existing chart
      mergeChartData(chart, data);
    }
  });
}

// Add the panel for a single job run
function addJobRun(jobRow, run) {
  var jobRunSelector = "#" + run.ocid.replaceAll(".", "");
  runDiv = jobRow.find(jobRunSelector);
  // Add job run panel if one does not exist.
  if (runDiv.length === 0) {
    console.log("Adding job run: " + run.ocid);
    jobRow.prepend(run.html);

    // YAML callback
    getJSON("/job_run_yaml/" + run.ocid, {}, function (data) {
      runDiv = jobRow.find(jobRunSelector);
      runDiv.find(".job-yaml").text(data.job_yaml);
      runDiv.find(".job-run-yaml").text(data.job_run_yaml);
      runDiv.find("code").each(function () {
        hljs.highlightElement(this);
      })
    })
    // Metric dropdown callback
    $(jobRunSelector + " .job-run-metrics").on("click", "a", function (e) {
      e.preventDefault();
      metricDropdownClicked(this);
    });

    // Load logs.
    $(jobRunSelector + " .run-monitor").each(function () {
      var ocid = this.id;
      var outputDiv = $(this).find(".card-body.logs pre");
      updateLogs(ocid, outputDiv);
    });
  }
}

function loadJobRuns(endpoint, jobRow) {
  getJSON(
    endpoint, {},
    // success
    function (data) {
      if (jobRow.find(".col-xxl-4").length === 0) jobRow.empty();
      if (data.runs.length === 0) jobRow.text("No Job Run Found.");
      data.runs.reverse().forEach(run => {
        addJobRun(jobRow, run);
      });
    },
    // error
    function (data) {
      if (data.message !== undefined) {
        jobRow.text(data.message);
      } else jobRow.text("No Job Run Found.");
    }
  );
}

function checkAndLoadJobRuns(job_ocid) {
  const RUNNING = "running"
  // Avoid running the same function twice
  if (typeof (jobRunChecking[job_ocid]) === RUNNING) return;
  if (typeof (jobRunChecking[job_ocid]) === "number") clearTimeout(jobRunChecking[job_ocid]);
  jobRunChecking[job_ocid] = RUNNING;

  // Load job runs only if the accordion is opened.
  var jobAccordion = $("#" + job_ocid.replaceAll(".", "") + "-body");
  if (!jobAccordion.hasClass("show")) return;

  var jobRow = jobAccordion.find(".row");
  if (jobRow.length === 0) return;
  jobRow.append("");
  console.log("Loading job runs for job OCID: " + job_ocid);
  var startTime = performance.now();
  getJSON("/job_runs/" + job_ocid, {}, function (data) {
    if (jobRow.find(".col-xxl-4").length === 0) jobRow.empty();
    if (data.runs.length === 0) jobRow.text("No Job Run Found.");
    var endTime = performance.now();
    console.log(`Load job run: ${endTime - startTime} milliseconds`);
    data.runs.reverse().forEach(run => {
      addJobRun(jobRow, run);
    });
  });

  jobRunChecking[job_ocid] = setTimeout(function () {
    checkAndLoadJobRuns(job_ocid);
    // Check if there is new job run for the job in about 30 seconds.
    // Add a random number to the time interval so that not all requests are send at the same time.
  }, RUN_CHECKING_INTERVAL);
}

// Display a toast message
function toastMessage(title, message, time) {
  var template = $("#toast-template");
  var toastDiv = template.clone();
  toastDiv.find(".q-toast-title").text(title);
  toastDiv.find(".q-toast-body").text(message);
  if (time !== undefined) toastDiv.find(".q-toast-time").text(time);
  toastDiv.appendTo(template.parent());
  var toast = new bootstrap.Toast(toastDiv);
  toast.show();
}

// Download the logs of a job run to a text file.
function downloadLogs(jobRunId) {
  var logs = $("#" + jobRunId.replaceAll(".", "\\.")).find("pre").text();
  var filename = "logs-" + jobRunId + ".log";
  // Create a hidden hyperlink with logs embedded
  var element = document.createElement('a');
  element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(logs));
  element.setAttribute('download', filename);
  element.style.display = 'none';
  document.body.appendChild(element);
  // Trigger the download
  element.click();
  document.body.removeChild(element);
}

// The name of the metric being displayed is showed as the text of the menu button.
// When an item in the job run metrics dropdown is clicked,
// update the menu and the chart to show the newly selected metric.
function metricDropdownClicked(element) {
  var metricLink = $(element);
  var metricDiv = metricLink.closest(".job-run-metrics");
  metricDiv.find("li").removeClass("d-none");
  // Hide the selected metric from the dropdown
  metricLink.parent().addClass("d-none");
  // Show the selected metric as the menu button
  metricDiv.find("button").text(metricLink.text());

  const canvasId = metricDiv.find("canvas").attr("id");
  const ocid = metricDiv.closest(".run-monitor").attr("id");
  // Update the metric chart
  getJSON("/metrics/" + metricLink.data("val") + "/" + ocid, {}, function (data) {
    var chart = Chart.getChart(canvasId);
    chart.data.labels = data.timestamps;
    chart.data.datasets = data.datasets;
    chart.update();
  });
}

function authenticate_with_token() {
  $.getJSON("/authenticate/token/" + $("#profile").val(), function (data) {
    if (data.error === null) {
      location.reload();
    } else {
      toastMessage("Error", data.error);
    }
  });
}
