session.subscribeToEvent("SoundAuth/PlaySound", function (value) {
    console.log("From Event raised!")
    showLoading();
});

session.subscribeToEvent("SoundAuth/Found", function (value) {
    console.log("From Event raised!")
    hideLoading();
});
session.subscribeToEvent("SoundAuth/TimeError", function (value) {
    console.log("From Event raised!")
    hideLoading();
});

function showLoading() {
    $("#loading_container").css("visibility", "visible");


}

function hideLoading() {
    $("#loading_container").css("visibility", "hidden");
}


$(document).ready(function () {
   hideLoading()

});


function exit()
{
   session.raiseEvent("SoundAuth/ExitApp", 0);
}