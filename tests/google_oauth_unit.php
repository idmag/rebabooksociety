<?php
declare(strict_types=1);
require __DIR__.'/../google-oauth.php';
function check(bool $condition, string $message): void { if (!$condition) throw new RuntimeException($message); }
$profile=['sub'=>'123456789','email'=>'Reader@Gmail.com','email_verified'=>true,'name'=>'A Reader'];
$identity=googleIdentity($profile);
check($identity!==null && $identity['email']==='reader@gmail.com','verified profile');
check(googleIdentity(array_merge($profile,['email_verified'=>false]))===null,'unverified email denied');
check(googleIdentity(array_merge($profile,['email_verified'=>'true']))===null,'verification must be boolean');
check(googleIdentity(array_merge($profile,['sub'=>'']))===null,'missing identity denied');
$data=['users'=>[]];
$created=googleAccount($data,$identity,null);
check(count($data['users'])===1 && $data['users'][0]['google_only']===true,'new Google account');
check(!isset($data['users'][0]['is_admin']),'Google alone never grants admin');
check(googleAccount($data,$identity,null)['id']===$created['id'],'existing subject signs in');
$another=googleIdentity(array_merge($profile,['sub'=>'other']));
check(isset(googleAccount($data,$another,null)['error']),'same email is not automatically linked');
$existing=['users'=>[['id'=>'existing','name'=>'Existing','email'=>'reader@gmail.com','password'=>password_hash('example',PASSWORD_DEFAULT),'auth_version'=>1]]];
check(isset(googleAccount($existing,$identity,null)['error']),'existing password account not claimed by email');
check(isset(googleAccount($existing,$identity,['id'=>'existing','auth_version'=>0])['error']),'stale session cannot link');
$wrongEmail=googleIdentity(array_merge($profile,['email'=>'other@gmail.com']));
check(isset(googleAccount($existing,$wrongEmail,['id'=>'existing','auth_version'=>1])['error']),'link requires matching email');
check(googleAccount($existing,$identity,['id'=>'existing','auth_version'=>1])['linked']===true,'signed-in owner can link');
check(googleAccount($existing,$identity,null)['id']==='existing','linked subject resolves existing orders');
check(isset(googleAccount($existing,$another,['id'=>'existing','auth_version'=>1])['error']),'cannot replace linked identity');
$existing['users'][]=['id'=>'another','email'=>'reader@gmail.com','auth_version'=>0];
check(isset(googleAccount($existing,$identity,['id'=>'another','auth_version'=>0])['error']),'cannot link another user subject');
echo "Google identity validation and account linking tests passed.\n";
