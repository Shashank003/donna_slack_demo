import os.path
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import BaseTool
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from langchain_core.pydantic_v1 import BaseModel, Field
from typing import Type
from typing import List, Union, Optional
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_community.tools import BaseTool
from googleapiclient.discovery import Resource
from langchain_community.tools.gmail.utils import build_resource_service
from dateutil import parser
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(override=True)

TIMEZONE = os.environ["TIMEZONE"]

SCOPES = ["https://mail.google.com/", "https://www.googleapis.com/auth/calendar"]


def authenticate():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return creds


class CreateCalendarEventSchema(BaseModel):
    """Input for CreateCalendarEventTool"""

    summary: str = Field(description="A summary of the event")
    location: str = Field(description="Where the event will take place")
    description: str = Field(description="A description of the event")
    startDate: str = Field(
        description="Starting date for the event in ISO 8601 standard with Australia Sydney Timezone UTC +11"
    )
    endDate: str = Field(description="Ending date for the event in ISO 8601 standard with Australia Sydney Timezone UTC +11")
    attendees: Optional[Union[str, List[str]]] = Field(
        ...,
        description="The list of attendee emails provided.",
    )
    recurrence: Optional[str] = Field(description="Recurrence rules for repeating events, following iCalendar RRULE format.")


class CreateCalendarEventTool(BaseTool):
    """Tool that creates an event for Google calender"""

    name: str = "create_calender_event"
    description: str = (
        "A tool for creating Google Calendar events and meetings."
    )
    args_schema: Type[CreateCalendarEventSchema] = CreateCalendarEventSchema

    def _run(
        self,
        summary: str,
        location: str,
        description: str,
        startDate: str,
        endDate: str,
        attendees: Optional[Union[str, List[str]]] = None,
        recurrence: Optional[str] = None
    ):
        service = build("calendar", "v3", credentials=authenticate())
        if isinstance(attendees, str):
            # If there's only one attendee, wrap it in a list
            attendees = [{'email': attendees}]
        elif isinstance(attendees, list):
            # Convert each email address in the list to the required dictionary format
            attendees = [{'email': email} for email in attendees]


        event = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {"dateTime": startDate, "timeZone": TIMEZONE},
        "end": {"dateTime": endDate, "timeZone": TIMEZONE},
        "attendees": attendees,
        "recurrence": 
        [
            recurrence
        ]
    }
        print("Event is")
        print(event)
        event = service.events().insert(calendarId="primary", body=event).execute()
        return "Event created: %s" % (event.get("htmlLink"))


class ViewCalendarEventSchema(BaseModel):
    """Input for ViewCalendarEventsTool"""
    searchTerm : Optional[str] = Field(description="""Free text search terms to find events that match these terms in the following fields for events in google calendar:
                             a) summary b) description c) location d) attendee's displayName e) attendee's email f) organizer's displayName g) organizer's email""")
    timeMin: Optional[str] = Field(description="Lower bound (exclusive) for an event's end time to filter by. Must be an RFC3339 timestamp with mandatory time zone offset, for example, 2011-06-03T10:00:00-07:00, 2011-06-03T10:00:00Z.")
    timeMax : Optional[str] = Field(description="Upper bound (exclusive) for an event's start time to filter by. Must be an RFC3339 timestamp with mandatory time zone offset, for example, 2011-06-03T10:00:00-07:00, 2011-06-03T10:00:00Z.")



class ViewCalendarEventsTool(BaseTool):
    """A tool for retrieving Google Calendar events and meetings."""

    name: str = "google_calender_view"

    description: str = (
        "A tool for creating Google Calendar events and meetings."
    )
    args_schema: Type[ViewCalendarEventSchema] = ViewCalendarEventSchema

    def _run(
            self,
            searchTerm : Optional[str] = None,
            timeMin : Optional[str] = None,
            timeMax: Optional[str] = None
    ):

        if timeMax and timeMin == None:
            return "An error has occured since you did not provide a lower boundation time"

        service = build("calendar", "v3", credentials=authenticate())
        # event = {
        #     "maxAttendees" : 5,
        #     "maxResults": 20,
        #     "orderBy": "startTime",
        #     "singleEvents": True,
        #     "q": searchTerm,
        #     "timeMin": time_min_dt,
        #     "timeMax": time_max_dt
        # }

        events_result = service.events().list(
            calendarId="primary",
            timeMin=timeMin,
            timeMax=timeMax,
            maxResults=30,
            singleEvents=True,
            orderBy="startTime",
            q=searchTerm
        ).execute()
        events = events_result.get('items', [])
        print(events)
        if not events:
            return 'No upcoming events found.'
        else:
            return events
    

class CalendarToolkit(BaseToolkit):
    """Toolkit for interacting with Google Calendar.

    *Security Note*: This toolkit contains tools that can read and modify
        the state of a service; e.g., by creating, updating, deleting
        calendar events.

        Use responsibly and ensure proper authentication and permissions
        are in place.

        See https://python.langchain.com/docs/security for more information.
    """

    api_resource: Resource = Field(default_factory=build_resource_service)

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True

    def get_tools(self) -> List[BaseTool]:
        """Get the tools in the toolkit."""
        return [
            CreateCalendarEventTool(),
            ViewCalendarEventsTool(),
            # Other calendar tools can be added here
        ]


def convert_to_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """Utility function to convert a date string to a datetime object."""
    if date_str:
        try:
            return parser.parse(date_str)
        except ValueError as e:
            raise ValueError(f"Error parsing date string: {date_str}. Error: {e}")
    return None


if __name__ == "__main__":
    pass


