const signupBtn = document.getElementById("signupBtn");

if(signupBtn){

signupBtn.onclick=()=>{

const user={

name:document.getElementById("signupName").value,

email:document.getElementById("signupEmail").value,

password:document.getElementById("signupPassword").value

};

localStorage.setItem("xrUser",JSON.stringify(user));

authStatus.innerHTML="✔ Account Created";

setTimeout(()=>{

location.href="login.html";

},1200);

};

}

const loginBtn=document.getElementById("loginBtn");

if(loginBtn){

loginBtn.onclick=()=>{

const saved=JSON.parse(localStorage.getItem("xrUser"));

const email=document.getElementById("loginEmail").value;

const password=document.getElementById("loginPassword").value;

if(

saved &&

saved.email===email &&

saved.password===password

){

authStatus.innerHTML="ACCESS GRANTED...";

sessionStorage.setItem("loggedIn","true");

setTimeout(()=>{

location.href="../index.html";

},1200);

}

else{

authStatus.innerHTML="ACCESS DENIED";

}

};

}