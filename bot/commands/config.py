import discord

from cmdClient import cmd
from cmdClient.lib import ResponseTimedOut, UserCancelled
from cmdClient.checks import in_guild

from wards import timer_admin, timer_ready
from utils import seekers, ctx_addons, timer_utils  # noqa
# from Timer import create_timer


@cmd("newgroup",
     group="Configuration",
     desc="Create a new timer group.")
@in_guild()
@timer_ready()
@timer_admin()
async def cmd_addgrp(ctx):
    """
    Usage``:
        newgroup
        newgroup <name>
        newgroup <name>, <role>, <channel>, <clock channel>
    Description:
        Creates a new group with the specified properties.
        With no arguments or just `name` given, prompts for the remaining information.
    Parameters::
        name: The name of the group to create.
        role: The role given to people who join the group.
        channel: The text channel which can access this group.
        clock channel: The voice channel displaying the status of the group timer.
    Related:
        group, groups, delgroup
    Examples``:
        newgroup Espresso
        newgroup Espresso, Study Group 1, #study-channel, #espresso-vc
    """
    args = ctx.arg_str.split(",")
    args = [arg.strip() for arg in args]

    if len(args) == 4:
        name, role_str, channel_str, clockchannel_str = args

        # Find the specified objects
        try:
            role = await ctx.find_role(role_str.strip(), interactive=True)
            channel = await ctx.find_channel(channel_str.strip(), interactive=True)
            clockchannel = await ctx.find_channel(clockchannel_str.strip(), interactive=True)
        except UserCancelled:
            raise UserCancelled("User cancelled selection, no group was created.") from None
        except ResponseTimedOut:
            raise ResponseTimedOut("Selection timed out, no group was created.") from None

        # Create the timer
        timer = ctx.client.interface.create_timer(name, role, channel, clockchannel)
    elif len(args) >= 1 and args[0]:
        timer = await newgroup_interactive(ctx, name=args[0])
    else:
        timer = await newgroup_interactive(ctx)

    await ctx.reply("Group **{}** has been created and bound to channel {}.".format(timer.name, timer.channel.mention))


async def newgroup_interactive(ctx, name=None, role=None, channel=None, clock_channel=None):
    """
    Interactively create a new study group.
    Takes keyword arguments to use any pre-existing data.
    """
    try:
        if name is None:
            name = await ctx.input("Please enter a friendly name for the new study group:")
        while role is None:
            role_str = await ctx.input(
                "Please enter the study group role.\n"
                "This role is given to people who join the group, "
                "and is used for notifications.\n"
                "I must have permission to mention this role and give it to members. "
                "Note that it must be below my highest role in the role list.\n"
                "(Accepted input: Role name or partial name, role id, role mention, or `c` to cancel.)"
            )
            if role_str.lower() == 'c':
                raise UserCancelled

            role = await ctx.find_role(role_str.strip(), interactive=True)

        while channel is None:
            channel_str = await ctx.input(
                "Please enter the text channel to bind the group to.\n"
                "The group will only be accessible from commands in this channel, "
                "and the channel will host the pinned status message for this group.\n"
                "I must have the `MANAGE_MESSAGES` permission in this channel to pin the status message.\n"
                "(Accepted input: Channel name or partial name, channel id, channel mention, or `c` to cancel.)"
            )
            if channel_str.lower() == 'c':
                raise UserCancelled

            channel = await ctx.find_channel(
                channel_str.strip(),
                interactive=True,
                chan_type=discord.ChannelType.text
            )

        while clock_channel is None:
            clock_channel_str = await ctx.input(
                "Please enter the group voice channel, or `s` to continue without an associated voice channel.\n"
                "The name of this channel will be updated with the current stage and time remaining, "
                "and members who join the channel will automatically be subscribed to the study group.\n"
                "I must have the `MANAGE_CHANNEL` permission in this channel to update the name.\n"
                "(Accepted input: Channel name or partial name, channel id, channel mention, "
                "or `s` to skip or `c` to cancel.)"
            )
            if clock_channel_str.lower() == 's':
                break

            if clock_channel_str.lower() == 'c':
                raise UserCancelled

            clock_channel = await ctx.find_channel(
                clock_channel_str.strip(),
                interactive=True,
                chan_type=discord.ChannelType.voice
            )
    except UserCancelled:
        raise UserCancelled(
            "User cancelled during group creation! "
            "No group was created."
        ) from None
    except ResponseTimedOut:
        raise ResponseTimedOut(
            "Timed out waiting for a response during group creation! "
            "No group was created."
        ) from None

    # We now have all the data we need
    return ctx.client.interface.create_timer(name, role, channel, clock_channel)


@cmd("delgroup",
     group="Configuration",
     desc="Remove a timer group.")
@in_guild()
@timer_ready()
@timer_admin()
async def cmd_delgrp(ctx):
    """
    Usage``:
        delgroup <name>
    Description:
        Deletes the given group from the collection of timer groups in the current guild.
        If `name` is not given or matches multiple groups, will prompt for group selection.
    Parameters::
        name: The name of the group to delete.
    Related:
        group, groups, newgroup
    Examples``:
        delgroup Espresso
    """
    try:
        timer = await ctx.get_timers_matching(ctx.arg_str, channel_only=False)
    except ResponseTimedOut:
        raise ResponseTimedOut("Group selection timed out. No groups were deleted.") from None
    except UserCancelled:
        raise UserCancelled("User cancelled group selection. No groups were deleted.") from None

    if timer is None:
        return await ctx.error_reply("No matching timers found!")

    # Delete the timer
    ctx.client.interface.destroy_timer(timer)

    # Notify the user
    await ctx.reply("The group `{}` has been removed!".format(timer.name))


@cmd("adminrole",
     group="Configuration",
     desc="View or configure the timer admin role")
@in_guild()
async def cmd_adminrole(ctx):
    """
    Usage``:
        adminrole
        adminrole <role>
    Description:
        View the timer admin role (in the first usage), or set it to the provided role (in the second usage).
        The timer admin role allows creation and deletion of group timers,
        as well as modification of the guild registry and forcing timer operations.

        *Setting the timer admin role requires the guild permission `manage_guild`.*
    Parameters::
        role: The name, partial name, or id of the new timer admin role.
    """
    if ctx.arg_str:
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.error_reply("You need the `manage_guild` permission to change the timer admin role.")

        try:
            role = await ctx.find_role(ctx.arg_str, interactive=True)
        except UserCancelled:
            raise UserCancelled("User cancelled role selection. Timer admin role unchanged.") from None
        except ResponseTimedOut:
            raise ResponseTimedOut("Role selection timed out. Timer admin role unchanged.") from None

        ctx.client.config.guilds.set(ctx.guild.id, "timeradmin", role.id)

        await ctx.embedreply("Timer admin role set to {}.".format(role.mention), color=discord.Colour.green())
    else:
        roleid = ctx.client.config.guilds.get(ctx.guild.id, "timeradmin")
        if roleid is None:
            return await ctx.embedreply("No timer admin role set for this guild.")
        role = ctx.guild.get_role(roleid)
        if role is None:
            await ctx.embedreply("Timer admin role set to a nonexistent role `{}`.".format(roleid))
        else:
            await ctx.embedreply("Timer admin role is {}.".format(role.mention))


@cmd("globalgroups",
     group="Configuration",
     desc="Configure whether groups are accessible away from their channel.")
@in_guild()
async def cmd_globalgroups(ctx):
    """
    Usage``:
        globalgroups [off | on]
    Description:
        Configure whether groups may only be joined from their associated channel.
        This can, for instance, allow members to join a group before getting access to
        the group study channel.
        **Setting this option required the timer admin role, see `adminrole`.**
    Options::
        on: Groups may be joined from any channel.
        off: Groups may only be joined from the channel they are bound to. (**Default**)
    Related:
        newgroup, join, adminrole
    """
    if ctx.arg_str:
        if not (await timer_admin.run(ctx) or ctx.author.guild_permissions.manage_guild):
            return await ctx.error_reply("You need the timeradmin role to configure this setting!")

        if ctx.arg_str.lower() == 'off':
            ctx.client.config.guilds.set(ctx.guild.id, 'globalgroups', False)
            await ctx.reply("Groups may now only be joined from their associated channel.")
        elif ctx.arg_str.lower() == 'on':
            ctx.client.config.guilds.set(ctx.guild.id, 'globalgroups', True)
            await ctx.reply("Groups may now be joined from any guild channel.")
        else:
            await ctx.error_reply("Unrecognised option `{}`. See `help globalgroups` for usage.".format(ctx.arg_tr))
    else:
        setting = ctx.client.config.guilds.get(ctx.guild.id, 'globalgroups')
        if setting:
            await ctx.reply("Groups may be joined from any guild channel.")
        else:
            await ctx.reply("Groups may only be joined from their associated channel.")
