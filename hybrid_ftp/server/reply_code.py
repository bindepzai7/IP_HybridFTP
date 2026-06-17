from enum import IntEnum

class ReplyCode(IntEnum):
    RestartMarker = 110
    ServiceTemporarilyNotAvailable = 120
    DataAlreadyOpen = 125
    OpeningData = 150
    
    CommandOK = 200
    CommandExtraneous = 202
    DirectoryStatus = 212
    FileStatus = 213
    SystemType = 215
    SendUserCommand = 220
    ClosingControl = 221
    ClosingData = 226
    EnteringPassive = 227
    LoggedInProceed = 230
    ServerWantsSecureSession = 234
    FileActionOK = 250
    PathnameCreated = 257
    
    SendPasswordCommand = 331
    NeedLoginAccount = 332
    FileCommandPending = 350
    
    ServiceNotAvailable = 421
    CantOpenData = 425
    ConnectionClosed = 426
    ActionNotTakenFileUnavailableOrBusy = 450
    ActionAbortedLocalProcessingError = 451
    ActionNotTakenInsufficientSpace = 452
    
    CommandSyntaxError = 500
    ArgumentSyntaxError = 501
    CommandNotImplemented = 502
    BadCommandSequence = 503
    NotLoggedIn = 530
    AccountNeeded = 532
    ActionNotTakenFileUnavailable = 550
    ActionAbortedUnknownPageType = 551
    FileActionAborted = 552
    ActionNotTakenFilenameNotAllowed = 553
    
DefaultMessage = {
    ReplyCode.RestartMarker: "MARK {user_marker} = {server_marker}",
    ReplyCode.ServiceTemporarilyNotAvailable: "Service ready in {minutes} minutes.",
    ReplyCode.DataAlreadyOpen: "Data connection already open; transfer starting.",
    ReplyCode.OpeningData: "File status okay; about to open data connection.",
    
    ReplyCode.CommandOK: "Command okay.",
    ReplyCode.CommandExtraneous: "Command not implemented, superfluous at this site.",
    ReplyCode.DirectoryStatus: "Directory status.",
    ReplyCode.FileStatus: "File status.",
    ReplyCode.SystemType: "{system_name}",
    ReplyCode.SendUserCommand: "Service ready for new user.",
    ReplyCode.ClosingControl: "Service closing control connection.Logged out if appropriate.",
    ReplyCode.ClosingData: "Closing data connection. Requested file action successful.",
    ReplyCode.EnteringPassive: "Entering Passive Mode (h1,h2,h3,h4,p1,p2).",
    ReplyCode.LoggedInProceed: "User logged in, proceed.",
    ReplyCode.ServerWantsSecureSession: "Server wants secure session.",
    ReplyCode.FileActionOK: "Requested file action okay, completed.",
    ReplyCode.PathnameCreated: "\"{pathname}\" created.",
    
    ReplyCode.SendPasswordCommand: "User name okay, need password.",
    ReplyCode.NeedLoginAccount: "Need account for login.",
    ReplyCode.FileCommandPending: "Requested file action pending further information.",
    
    ReplyCode.ServiceNotAvailable: "Service not available, closing control connection.",
    ReplyCode.CantOpenData: "Can't open data connection.",
    ReplyCode.ConnectionClosed: "Connection closed; transfer aborted.",
    ReplyCode.ActionNotTakenFileUnavailableOrBusy: "Requested file action not taken. File unavailable.",
    ReplyCode.ActionAbortedLocalProcessingError: "Requested action aborted: local error in processing.",
    ReplyCode.ActionNotTakenInsufficientSpace: "Requested action not taken. Insufficient storage space in system.",
    
    ReplyCode.CommandSyntaxError: "Syntax error, command unrecognized.",
    ReplyCode.ArgumentSyntaxError: "Syntax error in parameters or arguments.",
    ReplyCode.CommandNotImplemented: "Command not implemented.",
    ReplyCode.BadCommandSequence: "Bad sequence of commands.",
    ReplyCode.NotLoggedIn: "Not logged in.",
    ReplyCode.AccountNeeded: "Need account for login.",
    ReplyCode.ActionNotTakenFileUnavailable: "Requested action not taken. File unavailable.",
    ReplyCode.ActionAbortedUnknownPageType: "Requested action aborted: page type unknown.",
    ReplyCode.FileActionAborted: "Requested file action aborted.",
    ReplyCode.ActionNotTakenFilenameNotAllowed: "Requested action not taken. File name not allowed.",
}