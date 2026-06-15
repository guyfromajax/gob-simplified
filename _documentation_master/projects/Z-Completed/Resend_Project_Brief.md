
**Objective**
Setup an email automation tool to manage key tasks identifed in this brief

**Key Tasks**
##Existing Alpha Code Requests
- there are currently 36 docs in the gob db, access_code_requests collection
- step 1:  de-dupe the list, some of these are the same user -- we should only keep one doc per email address.
- step 2: for the remining email addresses after the de-duped list, send a welcome email with their access code
    - their access code shuld be retrieved from the alpha_otps collection in the gob db
    - eligible access codes are those with a value of "used: false" AND the access code is not present in the used_otp_codes.md file
    - when an access code is sent to a user, add it to the used_otp_codes file (is there a better way to track these in the db as well? Perhaps a sent field for each doc in teh alpha_otps collection with a boolean of true or false? So we have sent and used as booleans?)

##New User Alpha Code Request
- email an alpha access code to the user if we have capacity remaining
- email a access code coming soon message to the user if we do not have capacity remaining
- capacity is limited to the number of docs in the alpha_otps collection that have a value of "sent: false", assuming per my note above that we add that field to the collection.

**Questions**
- do I need to upgrade to a paid plan with Resend in order to execute this? If so, I'm willing to do so, but if I do not need to, then I would prefer not to. 
- is Resend the best vendor for this

**Order of Operations**
- let's implement in develop branch / staging environment first and test with one new user (I'll provide the email address) and once confirmed there we'll migrate to main branch / production environment.