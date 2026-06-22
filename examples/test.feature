Feature: User login
	Scenario: Successful login with valid credentials
      	  Given the user is on the login page
	  When they enter valid credentials
	  When they click submit
	  Then they see their dashboard