# Copyright (c) 2006-2010 Mitch Garnaat http://garnaat.org/
# Copyright (c) 2010, Eucalyptus Systems, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish, dis-
# tribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the fol-
# lowing conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABIL-
# ITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, 
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

"""
Represents an EC2 Elastic Block Storage Volume
"""
from boto.ec2.ec2object import EC2Object, TaggedEC2Object

class TierType(EC2Object):
    def __init__(self, connection = None):
        EC2Object.__init__(self, connection)
        self.id = None
        self.tier_name = None
        self.replication = None
        self.is_default = False

    def __repr__(self):
        return "Tier type {0}".format(self.id)

    def endElement(self, name, value, connection):
        if name == "id":
            self.id = value
        elif name == "tierName":
            self.tier_name = value
        elif name == "replication":
            self.replication = (value.lower() != "false")
        elif name == "isDefault":
            self.is_default = (value.lower() != "false")

class Volume(TaggedEC2Object):
    
    def __init__(self, connection=None):
        TaggedEC2Object.__init__(self, connection)
        self.id = None
        self.create_time = None
        self.status = None
        self.size = None
        self.snapshot_id = None
        self.attach_data = None
        self.zone = None
        self.tier_type = None
        self.tier_name = None
        self.tier_replication = None
        self.size_in_bytes = None
        self.description = None

    def __repr__(self):
        return 'Volume:%s' % self.id

    def startElement(self, name, attrs, connection):
        retval = TaggedEC2Object.startElement(self, name, attrs, connection)
        if retval is not None:
            return retval
        if name == 'attachmentSet':
            self.attach_data = AttachmentSet()
            return self.attach_data
        elif name == 'tagSet':
            self.tags = boto.resultset.ResultSet([('item', Tag)])
            return self.tags
        else:
            return None

    def endElement(self, name, value, connection):
        if name == 'volumeId':
            self.id = value
        elif name == 'createTime':
            self.create_time = value
        elif name == 'status':
            if value != '':
                self.status = value
        elif name == 'size':
            self.size = int(value)
        elif name == 'snapshotId':
            self.snapshot_id = value
        elif name == 'availabilityZone':
            self.zone = value
        elif name == 'tierType':
            self.tier_type = value
        elif name == 'tierName':
            self.tier_name = value
        elif name == 'tierReplication':
            self.tier_replication = (value.lower() == 'true')
        elif name == 'sizeInBytes':
            self.size_in_bytes = int(value)
        elif name == 'description':
            self.description = value
        else:
            setattr(self, name, value)

    def _update(self, updated):
        self.__dict__.update(updated.__dict__)

    def update(self, validate=False):
        """
        Update the data associated with this volume by querying EC2.

        :type validate: bool
        :param validate: By default, if EC2 returns no data about the
                         volume the update method returns quietly.  If
                         the validate param is True, however, it will
                         raise a ValueError exception if no data is
                         returned from EC2.
        """
        # Check the resultset since Eucalyptus ignores the volumeId param
        unfiltered_rs = self.connection.get_all_volumes([self.id])
        rs = [ x for x in unfiltered_rs if x.id == self.id ]
        if len(rs) > 0:
            self._update(rs[0])
        elif validate:
            raise ValueError('%s is not a valid Volume ID' % self.id)
        return self.status

    def delete(self):
        """
        Delete this EBS volume.

        :rtype: bool
        :return: True if successful
        """
        return self.connection.delete_volume(self.id)

    def attach(self, instance_id, device):
        """
        Attach this EBS volume to an EC2 instance.

        :type instance_id: str
        :param instance_id: The ID of the EC2 instance to which it will
                            be attached.

        :type device: str
        :param device: The device on the instance through which the
                       volume will be exposed (e.g. /dev/sdh)

        :rtype: bool
        :return: True if successful
        """
        return self.connection.attach_volume(self.id, instance_id, device)

    def detach(self, force=False):
        """
        Detach this EBS volume from an EC2 instance.

        :type force: bool
        :param force: Forces detachment if the previous detachment attempt did
                      not occur cleanly.  This option can lead to data loss or
                      a corrupted file system. Use this option only as a last
                      resort to detach a volume from a failed instance. The
                      instance will not have an opportunity to flush file system
                      caches nor file system meta data. If you use this option,
                      you must perform file system check and repair procedures.

        :rtype: bool
        :return: True if successful
        """
        instance_id = None
        if self.attach_data:
            instance_id = self.attach_data.instance_id
        device = None
        if self.attach_data:
            device = self.attach_data.device
        return self.connection.detach_volume(self.id, instance_id, device, force)

    def create_snapshot(self, description=None):
        """
        Create a snapshot of this EBS Volume.

        :type description: str
        :param description: A description of the snapshot.  Limited to 256 characters.

        :rtype: :class:`boto.ec2.snapshot.Snapshot`
        :return: The created Snapshot object
        """
        return self.connection.create_snapshot(self.id, description)

    def volume_state(self):
        """
        Returns the state of the volume.  Same value as the status attribute.
        """
        return self.status

    def attachment_state(self):
        """
        Get the attachment state.
        """
        state = None
        if self.attach_data:
            state = self.attach_data.status
        return state

    def snapshots(self, owner=None, restorable_by=None):
        """
        Get all snapshots related to this volume.  Note that this requires
        that all available snapshots for the account be retrieved from EC2
        first and then the list is filtered client-side to contain only
        those for this volume.

        :type owner: list
        :param owner: If present, only the snapshots owned by the specified user
                      will be returned.  Valid values are:
                      self | amazon | AWS Account ID

        :type restorable_by: list
        :param restorable_by: If present, only the snapshots that are restorable
                              by the specified account id will be returned.

        :rtype: list of L{boto.ec2.snapshot.Snapshot}
        :return: The requested Snapshot objects
        
        """
        rs = self.connection.get_all_snapshots(owner=owner,
                                               restorable_by=restorable_by)
        mine = []
        for snap in rs:
            if snap.volume_id == self.id:
                mine.append(snap)
        return mine

class AttachmentSet(object):
    
    def __init__(self, connection=None):
        self.id = None
        self.instance_id = None
        self.status = None
        self.attach_time = None
        self.device = None

    def __repr__(self):
        return 'AttachmentSet:%s' % self.id

    def startElement(self, name, attrs, connection):
        pass
    
    def endElement(self, name, value, connection):
        if name == 'volumeId':
            self.id = value
        elif name == 'instanceId':
            self.instance_id = value
        elif name == 'status':
            self.status = value
        elif name == 'attachTime':
            self.attach_time = value
        elif name == 'device':
            self.device = value
        else:
            setattr(self, name, value)

class VolumeAttribute:

    def __init__(self, parent=None):
        self.id = None
        self._key_name = None
        self.attrs = {}

    def startElement(self, name, attrs, connection):
        if name in ('autoEnableIO', 'tierType', 'tierName', 'replication'):
            self._key_name = name
        return None

    def endElement(self, name, value, connection):
        if name == 'value':
            if name in ('autoEnableIO', 'replication'):
                self.attrs[self._key_name] = (value.lower() == 'true')
            else:
                self.attrs[self._key_name] = value
        elif name == 'volumeId':
            self.id = value
        else:
            setattr(self, name, value)

            
