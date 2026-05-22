function setInputDate(_id) {
    var _dat = document.querySelector(_id);
    var hoy = new Date(),
        d = hoy.getDate(),
        m = hoy.getMonth() + 1,
        y = hoy.getFullYear(),
        data;

    if (d < 10) {
        d = "0" + d;
    };
    if (m < 10) {
        m = "0" + m;
    };

    data = y + "-" + m + "-" + d;
    console.log(data);
    _dat.value = data;
};

setInputDate("#dateDefault");