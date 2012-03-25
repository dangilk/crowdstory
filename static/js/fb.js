Config = null;

function facebookInit(config) {
    Config = config;
    FB.init({
        appId: Config.appId,
        oauth: true,
        cookie: true,
        channelUrl: window.location.protocol + '//' + window.location.host + '/channel.html'
    });
    //FB.Canvas.setAutoResize();
}

function setDateFields(date) {
    document.getElementById('date_year').value = date.getFullYear();
    document.getElementById('date_month').value = date.getMonth() + 1;
    document.getElementById('date_day').value = date.getDate();
}
function dateToday() {
    setDateFields(new Date());
}
function dateYesterday() {
    var date = new Date();
    date.setDate(date.getDate() - 1);
    setDateFields(date);
}

function publishRun(title) {
    fbEnsureInit(function(){
        FB.ui({
            method: 'stream.publish',
            attachment: {
                name: title,
                caption: "I'm running!",
                media: [{
                    type: 'image',
                    href: 'http://runwithfriends.appspot.com/',
                    src: 'http://runwithfriends.appspot.com/splash.jpg'
                }]
            },
            action_links: [{
                text: 'Join the Run',
                href: 'http://runwithfriends.appspot.com/'
            }],
            user_message_prompt: 'Tell your friends about the run:'
        });
    });
}

function fbEnsureInit(callback) {
    if (!window.fbApiInitialized) {
        setTimeout(function() { fbEnsureInit(callback); }, 50);
    } else {
        console.log('fb initialized, call '+callback.toString());
        if (callback) { callback(); }
    }
}

function fbEnsureLogin(callback) {
    if (!window.fbLoginComplete) {
        setTimeout(function() { fbEnsureLogin(callback); }, 50);
    } else {
        if (callback) { callback(); }
    }
}