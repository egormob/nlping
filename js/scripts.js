//jQuery.noConflict();

/**
 * @description вызов функций при полной загрузке страницы, картинки при этом
 *              уже загрузились
 */
window.onload=documentLoaded;
function documentLoaded(){
    
}


/**
 * @description вызов функций при полной загрузке DOM дерева, картинки при этом
 *              еще не загрузились
 */
jQuery(document).ready(function() {
    autoclearInput();
    formsWidthNormalize();
    CornersInit();
    jQuery(document).pngFix();
    roundBoxInit();
    dropDownMenu();
	applyInvisibles();
	fill_subs();
});


function dropDownMenu () {
	var i = 1;
	for (i=1; i<=10; i++) {
		if (jQuery('#menu-item-'+i).get(0)) {
			jQuery('#menu-item-'+i).hover(function() {
				jQuery('td', this).addClass('active');
				var pos = jQuery(this).position();
				var page_pos = jQuery('#search-form').position();
				var str = this.id;
				var reg = /menu-item-/i;
				var id = str.replace(reg, ""); 
				if (jQuery.browser.msie && jQuery.browser.version.indexOf('6')+1 == 1 ) {
					jQuery('#subitems-' + id).css('left', pos.left+10).show();
				} else {
					jQuery('#subitems-' + id).css('left', pos.left-395-page_pos.left).show();
				}					
			},
			function() {
				var str = this.id;
				var reg = /menu-item-/i;
				var id = str.replace(reg, "");
				jQuery('#subitems-' + id).hide();
				jQuery('td', this).removeClass('active');
			});
			
			if (jQuery('#subitems-'+i).get(0)) {
				jQuery('#subitems-'+i+' ul, '+ '#subitems-'+i+' li, '+ '#subitems-'+i+' a, '+ '#subitems-'+i+' span').mouseout(function(){
					jQuery(this).parent('#subitems-'+i).show();
				});
				jQuery('#subitems-'+i).hover(function(){
					var str = this.id;
					var reg = /subitems-/i;
					var id = str.replace(reg, "");					
					jQuery('#menu-item-'+ id +' td').addClass('active');
					jQuery(this).show();
				},
				function() {
					var str = this.id;
					var reg = /subitems-/i;
					var id = str.replace(reg, "");					
					jQuery('#menu-item-'+ id +' td').removeClass('active');
					jQuery(this).hide();
				});
			}
			
		} else {
			break;
		}
	}
}

function roundBoxInit() {
    jQuery('.roundbox').wrap('<div class="rbox"></div>');
    jQuery('.roundbox').wrapInner('<div class="rbox_m"></div>');
    jQuery('.roundbox').before('<div class="rbox_tr"><div class="rbox_tl"><div class="rbox_t"> </div></div></div>');
    jQuery('.roundbox').after('<div class="rbox_br"><div class="rbox_bl"><div class="rbox_b"> </div></div></div>');
}


/**
 * @description функция для "добавить в избранное"
 */
function CreateBookmarkLink() {
    var url = window.document.location;
    var title = window.document.title;
    if (window.sidebar) {
        window.sidebar.addPanel(title, url, "");
    } else if (window.external) {
        window.external.AddFavorite(url, title);
    } else if (window.opera && window.print) {
        return true;
    }
}


/**
 * @description очистка инпутов, при клике на них. Для элементов с классом
 *              "autoclear"
 */
function autoclearInput() {
    jQuery(".autoclear").each(function() {
        jQuery(this).attr("defaultvalue", jQuery(this).attr("value"));
    });

    jQuery(".autoclear").bind('focus', function() {
        if (jQuery(this).attr("value") == jQuery(this).attr("defaultvalue")) {
            jQuery(this).attr("value", "");
            jQuery(this).addClass('normalcolor');
        }
    });
    
    jQuery(".autoclear").bind('blur', function() {
        if (jQuery(this).attr("value") == "") {
            jQuery(this).attr("value", jQuery(this).attr("defaultvalue"));
            jQuery(this).removeClass('normalcolor');
        }
        });
}


/**
 * @description выравнивание input[type=text], input[type=password], textarea с
 *              классом "form-normal"
 */
function formsWidthNormalize(){
    if (jQuery.browser.msie && jQuery.browser.version<7) {  
        jQuery("select.form-normal").each(function(i){
            var m5formnormalizepadding=Math.ceil(Number(String(jQuery(this).css("padding-left")).slice(0,-2)))+Math.ceil(Number(String(jQuery(this).css("padding-right")).slice(0,-2)));
            var m5formnormalizeborder= Math.ceil(Number(String(jQuery(this).css("border-left-width")).slice(0,-2)))+Math.ceil(Number(String(jQuery(this).css("border-right-width")).slice(0,-2)));
            var m5formnormalizewidth=Math.ceil(Number(jQuery(this).width()))+m5formnormalizepadding+m5formnormalizeborder*2;
            jQuery(this).width(m5formnormalizewidth);
        });     
    } else {        
        jQuery("input[type=text].form-normal, input[type=password].form-normal, textarea.form-normal").each(function(i){             
            var m5formnormalizepadding=Math.ceil(Number(String(jQuery(this).css("padding-left")).slice(0,-2)))+Math.ceil(Number(String(jQuery(this).css("padding-right")).slice(0,-2)));
            var m5formnormalizewidth=Math.ceil(Number(jQuery(this).width()))-m5formnormalizepadding;            
            jQuery(this).width(m5formnormalizewidth);
            });
        jQuery("select.form-normal").each(function(i){             
            var m5formnormalizepadding=Math.ceil(Number(String(jQuery(this).css("padding-left")).slice(0,-2)))+Math.ceil(Number(String(jQuery(this).css("padding-right")).slice(0,-2)));
            var m5formnormalizeborder= Math.ceil(Number(String(jQuery(this).css("border-left-width")).slice(0,-2)))+Math.ceil(Number(String(jQuery(this).css("border-right-width")).slice(0,-2)));
            if (jQuery.browser.msie && jQuery.browser.version<8){
                var m5formnormalizewidth=Math.ceil(Number(jQuery(this).width()))+m5formnormalizepadding+m5formnormalizeborder*2;
            } else {
                var m5formnormalizewidth=Math.ceil(Number(jQuery(this).width()))+m5formnormalizepadding+m5formnormalizeborder;
            }
            jQuery(this).width(m5formnormalizewidth);
        });     
    }
}


function CornersInit() {
    var corners = getElementsByClass('corners');
    for (i = 0; i < corners.length; i++) {
        corners[i].innerHTML += '<em class="tl"></em><em class="tr"></em><em class="bl"></em><em class="br"></em>';
    }
}

function getElementsByClass(searchClass,node,tag) {
    var classElements = new Array();
    if ( node == null ) node = document;
    if ( tag == null ) tag = '*';
    var els = node.getElementsByTagName(tag);
    var elsLen = els.length;
    var pattern = new RegExp("(^|\\s)"+searchClass+"(\\s|$)");
    for (i = 0, j = 0; i < elsLen; i++) {
        if (pattern.test(els[i].className) ) {
            classElements[j] = els[i];
            j++;
        }
    }
    return classElements;
}

function applyInvisibles() {
	$("form .label .invisible").hide();
	$("form :checked").each(function() {toggleInvisibles(this);})
	$(":input[type='radio'][name='method']").change(function(){toggleInvisibles(this);});	
}

function toggleInvisibles(thisElem) {
	var thisParent = $(thisElem).parents("form");
	thisParent.find(":radio[name='method']:checked").each(function (){$(this).parents(".item").find(".label .invisible").slideDown('slow');});
	thisParent.find(":radio[name='method']:not(:checked)").each(function (){$(this).parents(".item").find(".label .invisible").slideUp('slow');});
}

function getUrlVars(){
    var vars = [], hash;
    var hashes = window.location.href.slice(window.location.href.indexOf('?') + 1).split('#')[0].split('&');
    for(var i = 0; i < hashes.length; i++)
    {
        hash = hashes[i].split('=');
        vars.push(hash[0]);
        vars[hash[0]] = decodeURIComponent(hash[1]);
    }
    return vars;
}

function fill_subs(){
	jQuery(".lead_name").val(jQuery.cookie("subs_name"));
	jQuery(".lead_email").val(jQuery.cookie("subs_email"));
	jQuery(".lead_phone").val(jQuery.cookie("subs_phone"));
}

function save_subs(del_id){
    jQuery.cookie("subs_name", form.lead_name.value, {expires: 3650});
    jQuery.cookie("subs_email", form.lead_email.value, {expires: 3650});
    jQuery.cookie("subs_phone", form.lead_phone.value, {expires: 3650});
    jQuery.cookie("key_"+del_id, "1", {expires: 3650});
}

function shadow_subscribe(del_id, doneurl, form){
    jQuery.cookie("subs_name", form.lead_name.value, {expires: 3650});
    jQuery.cookie("subs_email", form.lead_email.value, {expires: 3650});
    var subs_name = jQuery.cookie("subs_name");
    var subs_email = jQuery.cookie("subs_email");
    var subs_url = "http://s.nlping.ru/subscribe/process/?rid[0]="+del_id+"&lead_email="+subs_email+"&lead_name="+subs_name;
    if(jc_chkscrfrm(form, false, false, false, false)){
	    jQuery.ajax({
	    	url: subs_url+"&callback=?", 
	    	complete: function(){ window.location.href = doneurl; },
	    });
	}
	return false;
}

function shadow_subscribe_phone(del_id, doneurl, form){
    jQuery.cookie("subs_name", form.lead_name.value, {expires: 3650});
    jQuery.cookie("subs_email", form.lead_email.value, {expires: 3650});
    jQuery.cookie("subs_phone", form.lead_phone.value, {expires: 3650});
    var subs_name = jQuery.cookie("subs_name");
    var subs_email = jQuery.cookie("subs_email");
    var subs_phone = jQuery.cookie("subs_phone");
    var subs_url = "http://s.nlping.ru/subscribe/process/?rid[0]="+del_id+"&lead_email="+subs_email+"&lead_name="+subs_name+"&lead_phone="+subs_phone;
    if(jc_chkscrfrm(form, true, true, false, false)){
	    jQuery.ajax({
	    	url: subs_url+"&callback=?", 
	    	complete: function(){ window.location.href = doneurl; },
	    });
	}
	return false;
}

function jc_chkscrfrm(a, phone, phone_req, city, city_req)
{
	if(a.lead_name && (a.lead_name.value=='' || a.lead_name.value.indexOf(" ваше ")>-1))
	{
		a.lead_name.focus();
		alert('Пожалуйста, введите ваше имя!');
		return false;
	}
	
	if(!a.lead_email)
	{
		alert('Отсутствует обязательное поле E-mail(lead_email)!');
		return false;
	}
	
	if(a.lead_email.value=='')
	{
		a.lead_email.focus();
		alert('Пожалуйста, введите ваш адрес E-mail!');
		return false;
	}
	else
	{
		var b=/^[a-z0-9_\-\.\+]+@([a-z0-9]+[\-\.])*[a-z0-9]+\.[a-z]{2,6}$/i;
		if(!b.test(a.lead_email.value))
		{
			a.lead_email.focus();
			alert('Пожалуйста, введите КОРРЕКТНЫЙ адрес E-mail!');
			return false;
		}
	}
	
	if(phone && a.lead_phone.value!='')
	{
		var c=/^(\+?\d+\s*)?(\(\d+\))?\s*-?\s*([\d\- ]*)$/i;
		if(!c.test(a.lead_phone.value))
		{
			a.lead_phone.focus();
			alert('Пожалуйста, введите КОРРЕКТНЫЙ номер телефона!');
			return false;
		}
	}
	if(phone_req && a.lead_phone.value=='')
	{
		a.lead_phone.focus();
		alert('Пожалуйста, введите ваш номер телефона!');
		return false;
	}
	if (city && city_req && a.lead_city && (a.lead_city.value == '' || a.lead_city.value.indexOf(" ваш ") >- 1))
	{
		a.lead_city.focus();
		alert('Пожалуйста, введите ваш город!');
		return false;
	}
	
	return true;
}
