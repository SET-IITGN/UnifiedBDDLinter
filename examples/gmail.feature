Feature:Gmail functionality test
Scenario: To verify that the user is able to login with valid credentials

Given User enters email or phone number
When User clicks on Next-button
And User enters password
And User clicks on Next-button
Then User should be logged in successfully