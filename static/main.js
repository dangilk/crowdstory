/*
 * Copyright 2011 Facebook, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 */
CS = {};

CS.helpers = function ($) {
    var helpers = {};

    helpers.get_friends = function (cb) {
        var q = "SELECT uid, name FROM user WHERE uid IN (SELECT uid2 FROM friend WHERE uid1 = " + CS.User.id + " )";
        fbEnsureInit(
            function () {
                console.log('use token '+CS.User.token);
                FB.api({
                        method:'fql.query',
                        query: q,
                        access_token: CS.User.token
                    },
                    function (response) {
                        cb(response);
                    })
            }
        );
    };


    helpers.dump = function (arr, level) {
        var dumped_text = "";
        if (!level) level = 0;

        //The padding given at the beginning of the line.
        var level_padding = "";
        for (var j = 0; j < level + 1; j++) level_padding += "    ";

        if (typeof(arr) == 'object') { //Array/Hashes/Objects
            for (var item in arr) {
                var value = arr[item];

                if (typeof(value) == 'object') { //If it is an array,
                    dumped_text += level_padding + "'" + item + "' ...\n";
                    dumped_text += helpers.dump(value, level + 1);
                } else {
                    dumped_text += level_padding + "'" + item + "' => \"" + value + "\"\n";
                }
            }
        } else { //Stings/Chars/Numbers etc.
            dumped_text = "===>" + arr + "<===(" + typeof(arr) + ")";
        }
        return dumped_text;
    }

    helpers.shuffle = function (o) { //v1.0
        for (var j, x, i = o.length; i; j = parseInt(Math.random() * i), x = o[--i], o[i] = o[j], o[j] = x);
        return o;
    };

    helpers.ajax = function (function_name, opt_argv) {


        // If optional arguments was not provided, create it as empty
        if (!opt_argv)
            opt_argv = new Array();

        // Find if the last arg is a callback function; save it
        var callback = null;
        var len = opt_argv.length;
        if (len > 0 && typeof opt_argv[len - 1] == 'function') {
            callback = opt_argv[len - 1];
            opt_argv.length--;
        }
        var async = (callback != null);

        // Encode the arguments in to a URI
        var query = 'action=' + encodeURIComponent(function_name);
        for (var i = 0; i < opt_argv.length; i++) {
            var key = 'arg' + i;
            var val = JSON.stringify(opt_argv[i]);
            query += '&' + key + '=' + encodeURIComponent(val);
        }
        query += '&time=' + new Date().getTime(); // IE cache workaround

        // See http://en.wikipedia.org/wiki/XMLHttpRequest to make this cross-browser compatible
        var req = new XMLHttpRequest();

        // Create a 'GET' request w/ an optional callback handler
        req.open('GET', '/rpc?' + query, async);

        if (async) {
            req.onreadystatechange = function () {
                if (req.readyState == 4 && req.status == 200) {
                    var response = null;
                    try {
                        response = JSON.parse(req.responseText);
                    } catch (e) {
                        response = req.responseText;
                    }
                    callback(response);
                }
            }
        }

        // Make the actual request
        req.send(null);
    }
    return helpers;
}(jQuery);

CS.Invite = function ($) {
    var invite = {};
    var $e;
    var friends;
    var current_friend = 0;
    var slice_size = 2;

    invite.init = function ($elements) {
        $e = $elements;
        CS.helpers.get_friends(friends_cb);

    }

    function friends_cb(f) {
        //console.log('got friends ' + CS.helpers.dump(f));
        var ids = [];
        for(friend in f){
            ids.push(f[friend].uid);
        }
        friends = CS.helpers.shuffle(ids);
        //invite.send();

    }

    invite.send = function(){
        var slice = friends.slice(current_friend, current_friend + slice_size);
        requests(slice,requests_cb);
    }

    function requests_cb(response){
        console.log('requests callback');
        current_friend += slice_size;
        if(response && current_friend < friends.length){
            var slice = friends.slice(current_friend, current_friend + slice_size);
            requests(slice,requests_cb);
        }
    }

    function requests(users,cb){
        console.log('pop request window'+CS.helpers.dump(users));
        fbEnsureInit(function(){
            FB.ui({
                method: 'apprequests',
                to: users,
                message: 'awesome requests, dude',
                access_token: CS.User.token
                //display: 'iframe'
            },cb)
        });
    }


    return invite;
}(jQuery);

CS.Stories = (function ($) {
    var stories = {};
    var $e;
    var snip_tree = [];
    var snip_row = [];
    var snip_choices = [0];
    var current_snip;
    var current_index = 0;
    var p;
    var is_writing = false;
    var loading = false;

    stories.init = function ($elements, params) {
        $e = $elements;
        p = params;
        snip_tree = CS.helpers.shuffle(p.first_snips);
        snip_row = snip_tree;
        add_click_handlers();
        //CS.helpers.ajax('getSnips',[0]);
        var snip = get_snip();
        set_meta(snip.author_name,snip.author_id);
        $e.snips.children().last().find('span').html(snip.text);
        set_next();
        //console.log(JSON.stringify(snip_tree));
    };

    function add_click_handlers() {
        $e.write.click(click_write);
        $e.next.click(click_next);
        $e.prev.click(click_prev);
        $e.left.click(click_left);
        $e.right.click(click_right);
        $e.cont.click(click_continue);
    }

    function click_write() {
        is_writing = true;
        $e.next.hide();
        $e.left.hide();
        $e.right.hide();
        $e.write.hide();
        $e.cont.show();
        set_meta(CS.User.name,CS.User.id);
        scroll_up('', true);
    }

    function cancel_write(){
        scroll_down('',true);
        is_writing = false;
        $e.cont.fadeOut();
        var snip = get_snip();
        if(!snip.is_end){
            $e.next.fadeIn();
        }
        $e.write.fadeIn();
        set_next(snip);
        set_meta(snip.author_name,snip.author_id);
    }

    function set_meta(name,id){
        $e.meta.find('img.author').attr('src','https://graph.facebook.com/'+id+'/picture?type=square');
        $e.meta.find('span').html('by: '+name);
    }

    function get_snip(offset) {
        //console.log('snip choices '+CS.helpers.dump(snip_choices));
        //console.log('snip row '+CS.helpers.dump(snip_row));
        if(!offset){
            offset = 0;
        }

        //if were looking for the current snip, its already in the snip_row
        if(snip_row && !offset){
            var index = snip_choices[snip_choices.length - 1];
            return snip_row[index];
        }
        //otherwise traverse the tree
        var snip_subset = snip_tree;
        for (var i = 0; i < snip_choices.length - 1 - offset; i++) {
            snip_subset = snip_subset[snip_choices[i]].children;
        }
        var index = snip_choices[snip_choices.length - 1 - offset];
        if(!offset){
            snip_row = snip_subset;
        }
        return snip_subset[index];
    }

    function reset_snip_row(){
        var snip_subset = snip_tree;
        for (var i = 0; i < snip_choices.length - 1; i++) {
            snip_subset = snip_subset[snip_choices[i]].children;
        }
        snip_row = snip_subset;
    }

    function set_next(snip){
        if(!snip){
            snip = get_snip();
        }
        if(snip.is_end){
            $e.next.fadeOut();
        }else{
            $e.next.fadeIn();
        }
        if(snip_row.length>1){
            $e.left.fadeIn();
            $e.right.fadeIn();
        }else{
            $e.left.fadeOut();
            $e.right.fadeOut();
        }
    }

    function click_continue() {
        if(loading){
            return;
        }
        loading = true;
        var text = $e.textarea.val();

        var parent = get_snip();
        console.log('parent: '+parent.text);
        var snip = {};
        snip.text = text;
        snip.parent_id = parent.id;
        snip.children = [];
        snip.author_id = CS.User.id;
        snip.author_name = CS.User.name;
        snip.props = 0;
        snip.blocks=0;
        snip.is_end=true;

        parent.children.push(snip);
        parent.is_end=false;

        snip_choices.push(parent.children.length-1);
        snip_row = parent.children;

        $e.snips.children().last().html(text);
        scroll_up(text);
        console.log('write snip '+parent.id+' '+text+' '+CS.User.id+' '+CS.User.name+' '+CS.User.locale);

        var write_cb = function(id){
            console.log('setting id');
            snip.id = id;
            loading = false;
        }
        CS.helpers.ajax('writeSnip',[parent.id, text, CS.User.id, CS.User.name, CS.User.locale, write_cb]);


    }

    function click_next() {
        if(loading){
            return;
        }
        loading = true;
        var current = get_snip();
        console.log('current snip: '+current.text);
        if(current.children.length>0 && !current.is_end){
            snip_row = current.children;
            snip_choices.push(0);
            var n = get_snip();
            set_next(n);
            set_meta(n.author_name,n.author_id);
            scroll_up(n.text);
            loading = false;
            //console.log('clicked next cache ' + CS.helpers.dump(snip_tree));
        }else{
            var get_cb = function(snips){
                snips = CS.helpers.shuffle(snips);
                current.children = snips;
                snip_row = snips;
                snip_choices.push(0);
                var n = get_snip();
                set_next(n);
                set_meta(n.author_name,n.author_id);
                scroll_up(n.text);
                loading = false;
                //console.log('clicked next ajax' + CS.helpers.dump(snip_tree));
            }
            console.log('get snips '+current.id);
            CS.helpers.ajax('getSnips',[current.id , CS.User.locale, get_cb]);
        }
    }

    function click_prev() {
        if(is_writing){
            cancel_write();
        } else if(snip_choices.length>1){
            snip_choices.pop();
            reset_snip_row();
            var snip = get_snip(2);
            if(snip_choices.length<3){
                scroll_down('');
            }else{
                scroll_down(snip.text);
            }
            snip = get_snip();
            set_next(snip);
            set_meta(snip.author_name,snip.author_id);
        }

       // console.log('clicked prev ' + CS.helpers.dump(snip_tree));

    }

    function click_left() {
        if(snip_choices[snip_choices.length-1]<=0){
            snip_choices[snip_choices.length-1] = snip_row.length-1;
        }else{
            snip_choices[snip_choices.length-1] = snip_choices[snip_choices.length-1] - 1;
        }

        var snip = get_snip();
        set_next(snip);
        set_meta(snip.author_name,snip.author_id);
        scroll_side(snip.text);
    }

    function click_right() {
        if(snip_choices[snip_choices.length-1]>=snip_row.length-1){
            snip_choices[snip_choices.length-1] = 0;
        }else{
            snip_choices[snip_choices.length-1] = snip_choices[snip_choices.length-1] + 1;
        }
        var snip = get_snip();
        set_next(snip);
        set_meta(snip.author_name,snip.author_id);
        scroll_side(snip.text);
    }

    function scroll_up(text, writing) {
        var $div = build_snip_div(text);
        $div.css({'height':0, 'paddingTop':0});
        $e.snips.append($div);
        var $shrink = $e.snips.children().first();
        $shrink.animate({height:0, paddingTop:0}, 400, function () {
            $shrink.remove()
        });
        $div.animate({height:50, paddingTop:20}, 400, function () {
            $div.css({'height':50, 'paddingTop':20});
            if (writing) {
                $e.textarea.fadeIn(400);
            }
        });
    }

    function scroll_down(text,cancel_writing) {
        var $div = build_snip_div(text);
        $div.css({'height':0, 'paddingTop':0});
        $e.snips.prepend($div);
        var $shrink = $e.snips.children().last();
        if(cancel_writing){
            $e.textarea.fadeOut(400,function(){
                $shrink.animate({height:0, paddingTop:0}, 400, function () {
                    $shrink.remove()
                });
                $div.animate({height:50, paddingTop:20}, 400, function () {
                    $div.css({'height':50, 'paddingTop':20});
                });
            });
        }else{
            $shrink.animate({height:0, paddingTop:0}, 400, function () {
                $shrink.remove()
            });
            $div.animate({height:50, paddingTop:20}, 400, function () {
                $div.css({'height':50, 'paddingTop':20});
            });
        }
    }

    function scroll_side(text) {
        var $current = $e.snips.children().last().find('span');
        $current.animate({opacity:0}, 400, function () {
            $current.html(text);
            $current.animate({opacity:1}, 400);
        });
    }

    function build_snip_div(text) {
        var div = '<div class="snip-div">' +
            '<span class="snip">' + text + '</span>' +
            '</div>';
        return $(div);
    }

    return stories;
}(jQuery));